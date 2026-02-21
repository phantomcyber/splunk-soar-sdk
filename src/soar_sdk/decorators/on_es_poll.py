import asyncio
import inspect
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, get_args

from pydantic import ValidationError

from soar_sdk.abstract import SOARClient
from soar_sdk.action_results import ActionResult
from soar_sdk.exceptions import ActionFailure
from soar_sdk.logging import getLogger
from soar_sdk.meta.actions import ActionMeta
from soar_sdk.models.container import Container
from soar_sdk.models.finding import DrilldownDashboard, DrilldownSearch, Finding
from soar_sdk.params import OnESPollParams
from soar_sdk.types import Action, action_protocol

if TYPE_CHECKING:
    from soar_sdk.app import App


ESPollingYieldType = Finding
ESPollingSendType = int | None


class OnESPollDecorator:
    """Class-based decorator for tagging a function as the special 'on es poll' action."""

    def __init__(self, app: "App") -> None:
        self.app = app

    def __call__(self, function: Callable) -> Action:
        """Decorator for the 'on es poll' action. The decorated function must be a Generator or AsyncGenerator. Only one on_es_poll action is allowed per app.

        Usage:
        The generator should yield a `Finding`. Upon receiving an event from the generator, the SDK will submit the Finding to Splunk Enterprise Security and create a linked SOAR Container.
        The generator should accept a "send type" of `int | None`. When a Finding is successfully delivered to ES and linked to a Container, the SDK will send the Container ID back into the generator. The Container is useful for storing large attachments included with the Finding.
        If the Finding cannot be successfully delivered to ES, the SDK will stop polling and return a failed result for the action run.
        """
        if self.app.actions_manager.get_action("on_es_poll"):
            raise TypeError(
                "The 'on_es_poll' decorator can only be used once per App instance."
            )

        is_generator = inspect.isgeneratorfunction(function)
        is_async_generator = inspect.isasyncgenfunction(function)

        generator_type = inspect.signature(function).return_annotation
        generator_type_args = get_args(generator_type)

        if not (is_generator or is_async_generator) or len(generator_type_args) < 2:
            raise TypeError(
                "The on_es_poll function must be a Generator or AsyncGenerator (use 'yield')."
            )

        yield_type = generator_type_args[0]
        send_type = generator_type_args[1]

        if yield_type != ESPollingYieldType:
            raise TypeError(
                f"@on_es_poll generator should have yield type {ESPollingYieldType}."
            )
        if send_type != ESPollingSendType:
            raise TypeError(
                f"@on_es_poll generator should have send type {ESPollingSendType}."
            )

        action_identifier = "on_es_poll"
        action_name = "on es poll"

        validated_params_class = OnESPollParams
        logger = getLogger()

        @action_protocol
        @wraps(function)
        def inner(
            params: OnESPollParams,
            soar: SOARClient = self.app.soar_client,
            *args: Any,  # noqa: ANN401
            **kwargs: Any,  # noqa: ANN401
        ) -> bool:
            try:
                action_params = validated_params_class.model_validate(params)
            except ValidationError as e:
                logger.info(f"Parameter validation error: {e!s}")
                return self.app._adapt_action_result(
                    ActionResult(status=False, message=f"Invalid parameters: {e!s}"),
                    self.app.actions_manager,
                )

            kwargs = self.app._build_magic_args(function, soar=soar, **kwargs)
            generator = function(action_params, *args, **kwargs)

            asset_id = self.app.actions_manager.get_asset_id()
            asset_data = soar.get(f"/rest/asset/{asset_id}").json()
            ingest_config = asset_data.get("configuration", {}).get("ingest", {})

            es_security_domain = ingest_config.get("es_security_domain")
            es_urgency = ingest_config.get("es_urgency")
            es_run_threat_analysis = ingest_config.get("es_run_threat_analysis", False)
            es_launch_automation = ingest_config.get("es_launch_automation", False)
            container_label = ingest_config.get("container_label")
            app_name = str(self.app.app_meta_info.get("name", ""))
            asset_name: str = asset_data.get("name", "")
            finding_source: str = (
                f"{app_name} - {asset_name}"
                if app_name and asset_name
                else app_name or asset_name
            )

            if not es_security_domain:
                return self.app._adapt_action_result(
                    ActionResult(
                        status=False,
                        message="ES ingest requires 'es_security_domain' to be configured in asset ingest settings",
                    ),
                    self.app.actions_manager,
                )

            drilldown_searches: list[DrilldownSearch] | None = None
            drilldown_dashboards: list[DrilldownDashboard] | None = None
            raw_drilldown_searches = ingest_config.get("es_drilldown_searches")
            raw_drilldown_dashboards = ingest_config.get("es_drilldown_dashboards")
            if raw_drilldown_searches:
                try:
                    drilldown_searches = [
                        DrilldownSearch(**s) for s in raw_drilldown_searches
                    ]
                except (TypeError, ValidationError) as e:
                    return self.app._adapt_action_result(
                        ActionResult(
                            status=False,
                            message=f"Failed to parse es_drilldown_searches: {e}",
                        ),
                        self.app.actions_manager,
                    )
            if raw_drilldown_dashboards:
                try:
                    drilldown_dashboards = [
                        DrilldownDashboard(**d) for d in raw_drilldown_dashboards
                    ]
                except (TypeError, ValidationError) as e:
                    return self.app._adapt_action_result(
                        ActionResult(
                            status=False,
                            message=f"Failed to parse es_drilldown_dashboards: {e}",
                        ),
                        self.app.actions_manager,
                    )

            if is_async_generator:

                def polling_step(
                    last_container_id: ESPollingSendType,
                ) -> ESPollingYieldType:
                    return asyncio.run(generator.asend(last_container_id))
            else:

                def polling_step(
                    last_container_id: ESPollingSendType,
                ) -> ESPollingYieldType:
                    return generator.send(last_container_id)

            last_container_id = None
            findings_created = 0
            max_findings = action_params.container_count or None
            batch_size = soar.MAX_BULK_FINDINGS
            generator_exhausted = False

            def _apply_defaults(item: Finding) -> None:
                if item.security_domain is None:
                    item.security_domain = es_security_domain
                if item.urgency is None and es_urgency:
                    item.urgency = es_urgency
                if not item.run_threat_analysis:
                    item.run_threat_analysis = es_run_threat_analysis
                if not item.launch_automation:
                    item.launch_automation = es_launch_automation
                if item.drilldown_searches is None and drilldown_searches:
                    item.drilldown_searches = drilldown_searches
                if item.drilldown_dashboards is None and drilldown_dashboards:
                    item.drilldown_dashboards = drilldown_dashboards
                if item.finding_source is None and finding_source:
                    item.finding_source = finding_source

            while not generator_exhausted:
                batch: list[Finding] = []
                remaining = batch_size
                if max_findings is not None:
                    remaining = min(remaining, max_findings - findings_created)

                while len(batch) < remaining:
                    try:
                        send_value = last_container_id if not batch else None
                        item = polling_step(send_value)
                    except (StopIteration, StopAsyncIteration):
                        generator_exhausted = True
                        break
                    except ActionFailure as e:
                        e.set_action_name(action_name)
                        return self.app._adapt_action_result(
                            ActionResult(status=False, message=str(e)),
                            self.app.actions_manager,
                        )
                    except Exception as e:
                        self.app.actions_manager.add_exception(e)
                        logger.error(f"Error during finding processing: {e!s}")
                        return self.app._adapt_action_result(
                            ActionResult(status=False, message=str(e)),
                            self.app.actions_manager,
                        )

                    if type(item) is not ESPollingYieldType:
                        logger.warning(
                            f"Expected {ESPollingYieldType}, got {type(item)}, skipping"
                        )
                        continue

                    _apply_defaults(item)
                    batch.append(item)

                if not batch:
                    break

                save = self.app.actions_manager.save_progress
                findings_payload = [item.to_dict() for item in batch]
                save(f"Creating {len(batch)} finding(s) in bulk")
                try:
                    bulk_response = soar.create_findings_bulk(findings_payload)
                except Exception as e:
                    logger.error(f"Failed to bulk create findings: {e}")
                    return self.app._adapt_action_result(
                        ActionResult(
                            status=False,
                            message=f"Failed to bulk create findings: {e}",
                        ),
                        self.app.actions_manager,
                    )

                finding_ids: list[str] = bulk_response.get("findings", [])
                bulk_errors = bulk_response.get("errors", [])

                created = bulk_response.get("created", 0)
                failed = bulk_response.get("failed", 0)
                save(f"Created {created} finding(s), {failed} failed")

                if bulk_errors:
                    for error in bulk_errors:
                        logger.warning(
                            f"Bulk finding error at index {error.get('index')}: "
                            f"{error.get('error')}"
                        )

                findings_created += created

                total_finding_atts = 0
                total_vault_atts = 0
                findings_with_atts = 0
                containers_with_atts = 0

                for idx, item in enumerate(batch):
                    finding_id = finding_ids[idx] if idx < len(finding_ids) else ""

                    if item.run_threat_analysis and item.attachments:
                        uploaded = False
                        for attachment in item.attachments:
                            if not attachment.is_raw_email:
                                continue
                            try:
                                soar.upload_finding_attachment(
                                    finding_id,
                                    attachment.file_name,
                                    attachment.data,
                                    source_type=attachment.source_type,
                                    is_raw_email=attachment.is_raw_email,
                                )
                                total_finding_atts += 1
                                uploaded = True
                            except Exception as e:
                                logger.warning(
                                    f"Failed to upload attachment "
                                    f"{attachment.file_name}: {e}"
                                )
                        if uploaded:
                            findings_with_atts += 1

                    container = Container(
                        name=item.rule_title,
                        label=container_label,
                        description=item.rule_description,
                        severity=item.urgency or "medium",
                        status=item.status,
                        owner_id=item.owner,
                        sensitivity=item.disposition,
                        tags=item.source,
                        external_id=finding_id,
                        data={
                            "security_domain": item.security_domain,
                            "risk_score": item.risk_score,
                            "risk_object": item.risk_object,
                            "risk_object_type": item.risk_object_type,
                        },
                    )
                    container_dict = container.to_dict()
                    ret_val, message, last_container_id = (
                        self.app.actions_manager.save_container(container_dict)
                    )
                    if not ret_val:
                        raise ActionFailure(f"Failed to create container: {message}")

                    if last_container_id and item.attachments:
                        added = False
                        for attachment in item.attachments:
                            try:
                                soar.vault.create_attachment(
                                    last_container_id,
                                    attachment.data,
                                    attachment.file_name,
                                )
                                total_vault_atts += 1
                                added = True
                            except Exception as e:
                                logger.warning(
                                    f"Failed to add {attachment.file_name} "
                                    f"to container vault: {e}"
                                )
                        if added:
                            containers_with_atts += 1

                if total_finding_atts:
                    save(
                        f"Uploaded {total_finding_atts} attachment(s) "
                        f"to {findings_with_atts} finding(s)"
                    )
                if total_vault_atts:
                    save(
                        f"Added {total_vault_atts} file(s) to "
                        f"{containers_with_atts} container(s)"
                    )

                if max_findings is not None and findings_created >= max_findings:
                    break

            return self.app._adapt_action_result(
                ActionResult(
                    status=True,
                    message=f"Finding processing complete. Created {findings_created} findings.",
                ),
                self.app.actions_manager,
            )

        inner.params_class = validated_params_class

        class OnESPollActionMeta(ActionMeta):
            def model_dump(self, *args: object, **kwargs: object) -> dict[str, Any]:
                data = super().model_dump(*args, **kwargs)
                data["output"] = []
                return data

        inner.meta = OnESPollActionMeta(
            action=action_name,
            identifier=action_identifier,
            description=inspect.getdoc(function) or action_name,
            verbose="Callback action for the on_es_poll ingest functionality",
            type="ingest",
            read_only=True,
            parameters=validated_params_class,
            versions="EQ(*)",
        )

        self.app.actions_manager.set_action(action_identifier, inner)
        self.app.actions_manager.supports_es_polling = True
        self.app._dev_skip_in_pytest(function, inner)
        return inner
