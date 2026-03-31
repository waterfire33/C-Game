from dataclasses import dataclass

from app.db.workflow_models import ActionRiskClass, WorkflowStepDefinition


ROLE_RANK = {
    "member": 1,
    "admin": 2,
    "owner": 3,
}

DEFAULT_REQUIRED_ROLE_BY_RISK: dict[ActionRiskClass, str | None] = {
    ActionRiskClass.A: None,
    ActionRiskClass.B: "admin",
    ActionRiskClass.C: "admin",
    ActionRiskClass.D: "owner",
}


@dataclass(frozen=True)
class StepApprovalPolicy:
    risk_class: ActionRiskClass
    requires_approval: bool
    required_role: str | None


def get_step_approval_policy(step_definition: WorkflowStepDefinition) -> StepApprovalPolicy:
    risk_class = step_definition.action_risk_class or ActionRiskClass.A
    required_role = step_definition.required_approver_role or DEFAULT_REQUIRED_ROLE_BY_RISK[risk_class]

    requires_approval = False
    if risk_class in {ActionRiskClass.C, ActionRiskClass.D}:
        requires_approval = True
    elif risk_class == ActionRiskClass.B:
        requires_approval = bool(step_definition.requires_approval)
    elif step_definition.requires_approval:
        # Preserve legacy boolean-only behavior for rows created before risk classes existed.
        requires_approval = True
        if required_role is None:
            required_role = DEFAULT_REQUIRED_ROLE_BY_RISK[ActionRiskClass.C]

    return StepApprovalPolicy(
        risk_class=risk_class,
        requires_approval=requires_approval,
        required_role=required_role,
    )


def role_satisfies_requirement(actual_role: str | None, required_role: str | None) -> bool:
    if required_role is None:
        return True
    if actual_role is None:
        return False
    return ROLE_RANK.get(actual_role, 0) >= ROLE_RANK.get(required_role, 0)