"""The pipeline, the templates, and the application agreeing with each other.

`.github/workflows/check.yml` polls a health path, reads a CloudFormation
output by name, and deploys a template by path. None of those are checked by
anything: a renamed route, a renamed output or a moved file breaks the deploy
at the one moment nobody is watching — after the tests have passed.

These read the workflow and the templates as data and check them against the
running app. They are not a substitute for `cloudformation validate-template`,
which needs an account this repository does not assume it has; what they cover
is the seam between the pipeline and this codebase, which is where the drift
actually happens.
"""

from pathlib import Path

import pytest
import yaml

from app.main import app

REPO = Path(__file__).resolve().parents[2]
WORKFLOW = REPO / ".github" / "workflows" / "check.yml"
INFRA = REPO / "infra"


class CloudFormationLoader(yaml.SafeLoader):
    """`!Ref`, `!Sub`, `!GetAtt` and friends are not YAML, they are
    CloudFormation. Keeping them as plain data is enough to read the shape."""


def _tag(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {f"Fn::{suffix}": loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {f"Fn::{suffix}": loader.construct_sequence(node)}
    return {f"Fn::{suffix}": loader.construct_mapping(node)}


CloudFormationLoader.add_multi_constructor("!", _tag)


def template(name: str) -> dict:
    return yaml.load((INFRA / name).read_text(encoding="utf-8"), CloudFormationLoader)


@pytest.fixture(scope="module")
def workflow() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def deploy(workflow) -> dict:
    return workflow["jobs"]["deploy"]


@pytest.fixture(scope="module")
def steps(deploy) -> str:
    """Every `run:` in the deploy job, as one blob to search."""
    return "\n".join(str(step.get("run", "")) for step in deploy["steps"])


class TestTheHealthCheckChecksSomethingReal:
    def test_the_path_it_polls_is_an_endpoint(self, steps):
        assert "/api/health" in steps, "the deploy no longer checks a health path"
        assert "/api/health" in app.openapi()["paths"], "it polls a path that does not exist"

    def test_that_endpoint_needs_no_token(self):
        """A deploy has no session. A health check behind auth polls a 401
        forever and the deploy never goes green."""
        operation = app.openapi()["paths"]["/api/health"]["get"]
        assert not operation.get("security")

    def test_it_is_not_satisfied_by_a_200_alone(self, steps):
        """The body says whether the database answered; the status code alone
        would go green on a container that cannot serve."""
        assert '"status":"ok"' in steps

    def test_it_gives_up_rather_than_hanging(self, steps):
        assert "exit 1" in steps, "a health check that cannot fail is not a check"


class TestTheDeployAndTheTemplateAgree:
    def test_the_template_it_deploys_exists(self, steps):
        assert "infra/app.yaml" in steps
        assert (INFRA / "app.yaml").is_file()

    def test_the_output_it_reads_is_declared(self, steps):
        """`describe-stacks` returns nothing for an output that is not there,
        and the health check then polls the empty string."""
        assert "OutputKey==`Url`" in steps
        assert "Url" in template("app.yaml")["Outputs"]

    def test_the_parameter_it_passes_is_declared(self, steps):
        assert "ImageUri=" in steps
        assert "ImageUri" in template("app.yaml")["Parameters"]

    def test_the_image_is_tagged_with_the_commit(self, steps):
        """`latest` cannot be rolled back to and does not say what is running."""
        assert "github.sha" in steps
        assert ":latest" not in steps

    def test_the_container_port_matches_the_image(self):
        """The Dockerfile exposes 8000; the host maps 80 to it."""
        assert "EXPOSE 8000" in (REPO / "Dockerfile").read_text(encoding="utf-8")
        assert "-p 80:8000" in str(template("app.yaml")["Resources"]["Instance"])


class TestTheRoleIsNarrow:
    """The trust policy is the whole security boundary. These are the two ways
    it is usually widened by accident."""

    def trust(self) -> dict:
        role = template("github-oidc-role.yaml")["Resources"]["DeployRole"]
        return role["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Condition"][
            "StringEquals"
        ]

    def test_it_pins_the_repository_and_the_branch(self):
        subject = str(self.trust()["token.actions.githubusercontent.com:sub"])
        assert "repo:" in subject
        assert "ref:refs/heads/" in subject

    def test_it_does_not_wildcard_the_subject(self):
        """`repo:owner/*` or a trailing `*` lets any branch — and any pull
        request from a fork — assume the role."""
        assert "*" not in str(self.trust()["token.actions.githubusercontent.com:sub"])

    def test_it_pins_the_audience(self):
        assert self.trust()["token.actions.githubusercontent.com:aud"] == "sts.amazonaws.com"


class TestNoLongLivedCredentials:
    def test_the_deploy_asks_for_an_oidc_token(self, deploy):
        assert deploy["permissions"]["id-token"] == "write"

    def test_the_rest_of_the_pipeline_cannot(self, workflow):
        """Only the deploy job may mint an AWS credential. The default at the
        top of the file is read-only, and this is what keeps it that way."""
        for name, job in workflow["jobs"].items():
            if name == "deploy":
                continue
            assert "id-token" not in job.get("permissions", {}), name

    def test_there_is_no_access_key_anywhere(self):
        """An OIDC pipeline with a key in it is a key pipeline."""
        text = WORKFLOW.read_text(encoding="utf-8")
        assert "aws-access-key-id" not in text
        assert "AWS_SECRET_ACCESS_KEY" not in text


class TestItIsOffUntilItIsWanted:
    def test_the_deploy_is_gated_on_a_variable_being_set(self, deploy):
        """No account wired up means the job skips and the pipeline stays
        green, rather than failing every push with a credentials error."""
        assert "vars.AWS_DEPLOY_ROLE_ARN != ''" in deploy["if"]

    def test_it_only_runs_on_main(self, deploy):
        assert "refs/heads/main" in deploy["if"]
        assert "github.event_name == 'push'" in deploy["if"]

    def test_it_waits_for_every_test_job(self, deploy, workflow):
        """Deploying something the e2e run had not finished with would make the
        rest of this file decorative."""
        assert set(deploy["needs"]) == {"integration", "e2e"}
        for job in ("integration", "e2e"):
            assert set(workflow["jobs"][job]["needs"]) == {"backend", "frontend"}

    def test_the_two_test_jobs_do_not_wait_for_each_other(self, workflow):
        """They are independent, so they run at once."""
        assert "needs" not in workflow["jobs"]["backend"]
        assert "needs" not in workflow["jobs"]["frontend"]
