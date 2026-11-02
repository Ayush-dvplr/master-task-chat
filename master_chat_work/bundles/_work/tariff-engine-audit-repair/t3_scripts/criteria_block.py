@criterion(description="Statements on the shipped data are exact as a whole document")
def shipped_statements_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_document("shipped"))


@criterion(description="Statements on the fresh corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def fresh_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("fresh"))


@criterion(description="Every statement due on the fresh corpus is exact")
def fresh_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("fresh", "due"))


@criterion(description="Every statement redeemed list on the fresh corpus is exact")
def fresh_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("fresh", "redeemed"))


@criterion(description="Statements on the rescaled corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rescaled_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("rescaled"))


@criterion(description="Every statement due on the rescaled corpus is exact")
def rescaled_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rescaled", "due"))


@criterion(description="Every statement redeemed list on the rescaled corpus is exact")
def rescaled_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rescaled", "redeemed"))


@criterion(description="Statements on the relocated corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def relocated_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("relocated"))


@criterion(description="Every statement due on the relocated corpus is exact")
def relocated_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("relocated", "due"))


@criterion(description="Every statement redeemed list on the relocated corpus is exact")
def relocated_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("relocated", "redeemed"))


@criterion(description="Statements on the rotated corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def rotated_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("rotated"))


@criterion(description="Every statement due on the rotated corpus is exact")
def rotated_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rotated", "due"))


@criterion(description="Every statement redeemed list on the rotated corpus is exact")
def rotated_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("rotated", "redeemed"))


@criterion(description="Statements on the api corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def api_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("api"))


@criterion(description="Every statement due on the api corpus is exact")
def api_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("api", "due"))


@criterion(description="Every statement redeemed list on the api corpus is exact")
def api_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("api", "redeemed"))


@criterion(description="Statements on the recoded corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def recoded_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("recoded"))


@criterion(description="Every statement due on the recoded corpus is exact")
def recoded_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("recoded", "due"))


@criterion(description="Every statement redeemed list on the recoded corpus is exact")
def recoded_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("recoded", "redeemed"))


@criterion(description="Statements on the renamed corpus list the right accounts and balances, and redeem only the account's own distinct vouchers within the balance")
def renamed_statements_feasible(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_feasible("renamed"))


@criterion(description="Every statement due on the renamed corpus is exact")
def renamed_statement_due_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("renamed", "due"))


@criterion(description="Every statement redeemed list on the renamed corpus is exact")
def renamed_statement_redeemed_exact(workspace: Path) -> bool:
    return _holds(lambda: _check_statement_field("renamed", "redeemed"))


