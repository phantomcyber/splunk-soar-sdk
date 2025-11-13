# GitHub Actions Runner Configuration

The integration test workflow can run on different types of runners. This document explains the options.

## Current Configuration: GitHub-Hosted Runners ✅

The workflow is currently configured to use **GitHub-hosted ubuntu-latest runners**:

```yaml
integration-test:
  runs-on: ubuntu-latest
```

### Pros:
- ✅ No setup required
- ✅ Always available
- ✅ Free for public repos (included minutes for private)
- ✅ Clean environment every run

### Cons:
- ⚠️ Requires SOAR instances to be network-accessible from GitHub's IP ranges
- ⚠️ Slower than self-hosted runners (cold start)

### Requirements:
- SOAR test instances must be accessible from GitHub's IP ranges
- See: https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners#ip-addresses

---

## Alternative: CodeBuild Runners

If you have AWS CodeBuild configured for GitHub Actions, you can switch to use those runners instead.

### To Switch to CodeBuild:

Update the `integration-test` job in `.github/workflows/integration_tests.yml`:

```yaml
integration-test:
  runs-on:
    - codebuild-integration-tests-${{ github.run_id }}-${{ github.run_attempt }}
    - image:custom-linux-875003031410.dkr.ecr.us-west-2.amazonaws.com/soar-connectors/pytest:f7150dbb7f347d35f8f4bb285d36985ecd4cf231
  needs: build-example-apps
  # ... rest of config
```

### Pros:
- ✅ Can access internal/private SOAR instances
- ✅ Faster execution (warm runners)
- ✅ Custom Docker images with dependencies pre-installed
- ✅ More control over environment

### Cons:
- ⚠️ Requires AWS CodeBuild setup and configuration
- ⚠️ Costs associated with CodeBuild usage
- ⚠️ Need to maintain Docker images

### Setup Required:

1. **Enable CodeBuild for SDK Repository**
   - Contact your DevOps/Infrastructure team
   - Register the SDK repo with AWS CodeBuild GitHub integration
   - Ensure repo has access to CodeBuild projects

2. **Verify Docker Image Access**
   - Image: `custom-linux-875003031410.dkr.ecr.us-west-2.amazonaws.com/soar-connectors/pytest:f7150dbb7f347d35f8f4bb285d36985ecd4cf231`
   - Must be accessible from the SDK repo's CodeBuild setup

3. **Test the Configuration**
   - Push a test commit after switching
   - Verify runners connect properly
   - Check logs for any access issues

---

## Alternative: Self-Hosted Runners

You can also use your own self-hosted GitHub runners.

### To Switch to Self-Hosted:

```yaml
integration-test:
  runs-on: [self-hosted, linux, x64]  # Use your runner labels
  needs: build-example-apps
  # ... rest of config
```

### Setup Required:

1. Set up GitHub self-hosted runners: https://docs.github.com/en/actions/hosting-your-own-runners
2. Install required dependencies on runners:
   - Python 3.13
   - uv (Python package manager)
   - Network access to SOAR instances
3. Register runners with the SDK repository
4. Use appropriate labels in the workflow

---

## Recommended Configuration

| Scenario | Recommended Runner | Why |
|----------|-------------------|-----|
| SOAR instances are publicly accessible | GitHub-hosted (current) | Simplest, no setup |
| SOAR instances are internal-only | CodeBuild or Self-hosted | Network access required |
| Already have CodeBuild for connectors | CodeBuild | Consistent with other repos |
| Want maximum control | Self-hosted | Full customization |

---

## Network Requirements

Regardless of runner choice, ensure:

1. **HTTPS Access**: Runners can reach SOAR instances on port 443
2. **DNS Resolution**: Runner can resolve SOAR instance hostnames/IPs
3. **Firewall Rules**: Allow runner IPs through firewall (if applicable)
4. **SSL Certificates**: Self-signed certs are handled (verify=False in code)

---

## Testing Your Configuration

After making changes:

1. Create a test branch
2. Push a small change
3. Open a pull request
4. Monitor the "Integration Tests" workflow
5. Check logs for:
   - ✅ Runner connection
   - ✅ App builds succeed
   - ✅ App installations succeed
   - ✅ Tests execute
   - ✅ Results uploaded

If issues occur, check:
- GitHub Variables are set correctly
- GitHub Secrets are set correctly
- Network connectivity to SOAR instances
- Runner has required dependencies installed
