import { usePropFirmChallenge } from '@/hooks/usePropFirmChallenge';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

export function ChallengeSelector({ accountId, detectedFirm }: { accountId: string; detectedFirm?: string }) {
  const { updateConfig, isPending } = usePropFirmChallenge(accountId);
  const [selectedPhase, setSelectedPhase] = useState<string>('phase_1');

  const handleSubmit = () => {
    updateConfig.mutate({ challenge_type: selectedPhase });
  };

  return (
    <div className="space-y-3">
      <div className="text-xs font-mono text-zinc-300">
        <span className="font-bold text-emerald-400">{detectedFirm || 'Firm'}</span> detected. Please confirm challenge phase to initialize tracking:
      </div>
      <div className="flex gap-2">
        <select 
          className="bg-[#1e222d] border border-[#2a2e39] text-xs font-mono text-zinc-200 rounded px-2 py-1 flex-1"
          value={selectedPhase}
          onChange={(e) => setSelectedPhase(e.target.value)}
        >
          <option value="phase_1">Phase 1 (Evaluation)</option>
          <option value="phase_2">Phase 2 (Verification)</option>
          <option value="funded">Funded</option>
        </select>
        <Button 
          onClick={handleSubmit} 
          disabled={isPending}
          size="sm" 
          className="h-7 text-[10px] bg-[#26a69a] hover:bg-[#26a69a]/80"
        >
          {isPending ? 'Saving...' : 'Set Phase'}
        </Button>
      </div>
    </div>
  );
}
