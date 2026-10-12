import { useEffect, useState } from "react";

export function useTimer(running) {
  const [elapsedMs, setElapsedMs] = useState(0);

  useEffect(() => {
    if (!running) {
      setElapsedMs(0);
      return undefined;
    }
    const started = Date.now();
    const id = setInterval(() => setElapsedMs(Date.now() - started), 250);
    return () => clearInterval(id);
  }, [running]);

  const elapsed = Math.floor(elapsedMs / 1000);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, "0");
  const ss = String(elapsed % 60).padStart(2, "0");
  return { elapsedMs, elapsed, formatted: `${mm}:${ss}` };
}
