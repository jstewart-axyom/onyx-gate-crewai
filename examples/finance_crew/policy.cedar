// Onyx gateway policy for the finance crew example.
//
// The gateway maps each guarded CrewAI tool call onto a Cedar request:
//   principal = Agent::"<guard agent>"        (here: Agent::"ap-clerk")
//   action    = Action::"<tool name>"         (e.g. Action::"pay_invoice")
//   resource  = Tool::"<tool name>", carrying the call's arguments as
//               attributes (resource.vendor, resource.amount, ...)
//
// This policy is an ALLOWLIST: nothing runs unless a permit matches, so an
// unknown tool — or a payment call missing a required argument — is denied by
// default (fail-closed).

entity Agent::"ap-clerk" {} ;

// Reading the ledger is harmless — always permitted.
permit(principal, action == Action::"read_ledger", resource);

// Payments are permitted ONLY inside the mandate: an approved vendor AND
// at-or-under the autonomous cap. Anything outside needs a human.
permit(principal, action == Action::"pay_invoice", resource)
  when {
    resource.amount <= 5000 &&
    (resource.vendor == "globex" || resource.vendor == "initech")
  };
