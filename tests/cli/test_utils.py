import pytest
import keyword

from soar_sdk.cli.utils import normalize_field_name
from soar_sdk.meta.app import AppMeta


class TestNormalizeFieldName:
    """Test cases for the normalize_field_name function."""

    @pytest.mark.parametrize(
        "input_name,expected_output,expected_modified",
        [
            # Valid identifiers that shouldn't be modified
            ("valid_name", "valid_name", False),
            ("ValidName", "ValidName", False),
            ("name123", "name123", False),
            # Names starting with underscores
            ("_private", "private", True),
            ("__dunder__", "dunder__", True),
            # Names starting with digits
            ("123invalid", "n123invalid", True),
            # Names with invalid characters
            (
                "a-b.c d@e$f#g%h!i+j=k/l\\m|n&o*p(q)r[s]t{u}v<w>x:y;z,?'\"",
                "a_b_c_d_e_f_g_h_i_j_k_l_m_n_o_p_q_r_s_t_u_v_w_x_y_z____",
                True,
            ),
            ("🚀rocket-ship🚀", "rocket_ship_", True),
            # Mixed issues: starting with digit and invalid characters
            ("123field@name", "n123field_name", True),
        ],
    )
    def test_basic_normalization(
        self, input_name: str, expected_output: str, expected_modified: bool
    ) -> None:
        """Test basic field name normalization cases."""
        result = normalize_field_name(input_name)

        assert result.original == input_name
        assert result.normalized == expected_output
        assert result.modified == expected_modified
        assert result.normalized.isidentifier()

    @pytest.mark.parametrize(
        "keyword", [kw for kw in keyword.kwlist if not kw.startswith("_")]
    )
    def test_python_keywords(self, keyword: str):
        """Test that Python keywords get an underscore appended."""
        result = normalize_field_name(keyword)

        assert result.original == keyword
        assert result.normalized == f"{keyword}_"
        assert result.modified is True
        assert result.normalized.isidentifier()

    def test_empty_str(self):
        """Test edge cases and boundary conditions."""
        with pytest.raises(ValueError, match="empty"):
            normalize_field_name("")

        with pytest.raises(ValueError, match="must contain at least one letter"):
            normalize_field_name("______")


def test_bad_python_version_type():
    """Test that an invalid python_version type raises a ValueError."""
    with pytest.raises(
        ValueError,
        match="Invalid python_version type must be a list or a comma-separated string",
    ):
        AppMeta(
            project_name="test_app",
            description="Test app",
            license="Copyright (c) 2025 Splunk Inc.",
            app_version="1.0.0",
            package_name="test_app",
            python_version=123,
        )
