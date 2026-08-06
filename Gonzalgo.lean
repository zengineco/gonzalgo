/-
  gonzalgo — what does this proof rest on?

  A proof assistant confirms that a proof checks. It does not readily tell you
  the theorem is standing on an unfinished proof several files upstream, or that
  the result was obtained by trusting the compiler rather than the kernel. Both
  look exactly like success.

  This library is the Lean half: it writes out the declaration graph of your
  environment, keeping each theorem's statement dependencies apart from its proof
  dependencies. The analysis runs outside Lean, over the same code that reads
  Metamath databases, so two foundations are measured by one program rather than
  by analogy.

      import MyProject
      import Gonzalgo
      #eval Gonzalgo.dumpSplit "myproject.tsv"

  then

      pip install gonzalgo
      gonzalgo trust myproject.tsv        -- anything resting on a sorry?
      gonzalgo why <decl> -a Classical.choice

  https://f-keys.com/gonzalgo/
  Copyright (c) 2026 Vince Gonzalez. Apache-2.0.
-/
import Gonzalgo.Extract
