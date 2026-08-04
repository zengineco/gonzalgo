/-
  A project that rests on nothing but the kernel.

  `gonzalgo trust --fail-on-trust` must pass here. Nothing is unfinished and
  nothing is decided by running compiled code.
-/

theorem sub_add_ge (a b : Nat) : a - b + b ≥ a := by omega

theorem le_total' (a b : Nat) : a ≤ b ∨ b ≤ a := by omega

def double (n : Nat) : Nat := n + n

theorem double_eq (n : Nat) : double n = 2 * n := by
  simp [double, Nat.two_mul]
