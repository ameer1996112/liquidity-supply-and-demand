"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Play, Pause, SkipForward, SkipBack, RotateCcw, FastForward } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CandlestickData, Time } from "lightweight-charts";

export interface FXReplayProps {
  candles: CandlestickData<Time>[];
  onCandleIndexChange: (index: number) => void;
  currentIndex: number;
}

/**
 * FX Replay Controller - TradingView Bar Replay Style
 *
 * Features:
 * - Play/Pause bar-by-bar playback
 * - Speed control (0.5x, 1x, 2x, 5x)
 * - Step forward/backward
 * - Reset to start
 * - Progress bar with scrubbing
 */
export function FXReplayController({
  candles,
  onCandleIndexChange,
  currentIndex,
}: FXReplayProps) {
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1); // 1x = 1 candle per second
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const totalCandles = candles.length;
  const progress = totalCandles > 0 ? (currentIndex / totalCandles) * 100 : 0;

  // Play/Pause logic
  useEffect(() => {
    if (isPlaying && currentIndex < totalCandles - 1) {
      const delay = 1000 / speed; // Adjust delay based on speed
      intervalRef.current = setInterval(() => {
        onCandleIndexChange(Math.min(currentIndex + 1, totalCandles - 1));
      }, delay);
    } else {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (currentIndex >= totalCandles - 1) {
        setIsPlaying(false);
      }
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isPlaying, currentIndex, speed, totalCandles, onCandleIndexChange]);

  const handlePlayPause = () => {
    setIsPlaying((prev) => !prev);
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    onCandleIndexChange(Math.min(currentIndex + 1, totalCandles - 1));
  };

  const handleStepBackward = () => {
    setIsPlaying(false);
    onCandleIndexChange(Math.max(currentIndex - 1, 0));
  };

  const handleReset = () => {
    setIsPlaying(false);
    onCandleIndexChange(0);
  };

  const handleSkipForward = () => {
    setIsPlaying(false);
    onCandleIndexChange(Math.min(currentIndex + 10, totalCandles - 1));
  };

  const handleProgressClick = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const rect = event.currentTarget.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const percent = (x / rect.width) * 100;
      const newIndex = Math.floor((percent / 100) * totalCandles);
      setIsPlaying(false);
      onCandleIndexChange(Math.max(0, Math.min(newIndex, totalCandles - 1)));
    },
    [totalCandles, onCandleIndexChange]
  );

  const currentCandle = candles[currentIndex];
  const currentTime = currentCandle
    ? new Date((currentCandle.time as number) * 1000).toLocaleString()
    : "N/A";

  return (
    <div className="flex flex-col gap-4 p-4 bg-gray-900 border border-gray-800 rounded-lg">
      {/* Progress Bar */}
      <div className="flex flex-col gap-2">
        <div className="flex justify-between text-sm text-gray-400">
          <span>
            Candle {currentIndex + 1} / {totalCandles}
          </span>
          <span>{currentTime}</span>
        </div>

        <div
          className="h-2 bg-gray-800 rounded-full cursor-pointer relative overflow-hidden"
          onClick={handleProgressClick}
        >
          <div
            className="h-full bg-blue-600 rounded-full transition-all duration-100"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Playback Controls */}
      <div className="flex items-center justify-center gap-2">
        <Button
          variant="outline"
          size="icon"
          onClick={handleReset}
          disabled={currentIndex === 0}
          title="Reset to start"
        >
          <RotateCcw className="h-4 w-4" />
        </Button>

        <Button
          variant="outline"
          size="icon"
          onClick={handleStepBackward}
          disabled={currentIndex === 0}
          title="Step backward"
        >
          <SkipBack className="h-4 w-4" />
        </Button>

        <Button
          variant={isPlaying ? "destructive" : "default"}
          size="icon"
          onClick={handlePlayPause}
          disabled={currentIndex >= totalCandles - 1 && !isPlaying}
          className="h-10 w-10"
          title={isPlaying ? "Pause" : "Play"}
        >
          {isPlaying ? <Pause className="h-5 w-5" /> : <Play className="h-5 w-5" />}
        </Button>

        <Button
          variant="outline"
          size="icon"
          onClick={handleStepForward}
          disabled={currentIndex >= totalCandles - 1}
          title="Step forward"
        >
          <SkipForward className="h-4 w-4" />
        </Button>

        <Button
          variant="outline"
          size="icon"
          onClick={handleSkipForward}
          disabled={currentIndex >= totalCandles - 1}
          title="Skip +10 candles"
        >
          <FastForward className="h-4 w-4" />
        </Button>
      </div>

      {/* Speed Control */}
      <div className="flex items-center justify-center gap-2">
        <span className="text-sm text-gray-400 mr-2">Speed:</span>
        {[0.5, 1, 2, 5, 10].map((speedOption) => (
          <Button
            key={speedOption}
            variant={speed === speedOption ? "default" : "outline"}
            size="sm"
            onClick={() => setSpeed(speedOption)}
            className="min-w-[60px]"
          >
            {speedOption}x
          </Button>
        ))}
      </div>

      {/* Current Candle Info */}
      {currentCandle && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm border-t border-gray-800 pt-4">
          <div>
            <p className="text-gray-400">Open</p>
            <p className="font-mono text-white">{(currentCandle as any).open.toFixed(5)}</p>
          </div>
          <div>
            <p className="text-gray-400">High</p>
            <p className="font-mono text-[var(--to-long)]">{(currentCandle as any).high.toFixed(5)}</p>
          </div>
          <div>
            <p className="text-gray-400">Low</p>
            <p className="font-mono text-[var(--to-short)]">{(currentCandle as any).low.toFixed(5)}</p>
          </div>
          <div>
            <p className="text-gray-400">Close</p>
            <p className="font-mono text-white">{(currentCandle as any).close.toFixed(5)}</p>
          </div>
        </div>
      )}
    </div>
  );
}
