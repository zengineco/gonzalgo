/-
  A project with an unfinished proof buried two steps down.

  Nothing here says `sorry` at the top level, and Lean reports only a warning
  on the one line that does. The point of the audit is `inherited`: it looks
  finished, reads as finished, and is not proved at all.
-/

theorem foundation (a b : Nat) : a - b + b >= a := by sorry

theorem inherited (a b : Nat) : a - b + b + 1 > a := by
  have h := foundation a b
  omega