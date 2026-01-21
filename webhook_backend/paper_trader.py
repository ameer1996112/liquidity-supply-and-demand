"""
Paper Trading Module - Simulated Position Manager

Tracks virtual positions and simulates SL/TP execution without real broker.
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
import sqlite3

logger = logging.getLogger(__name__)

class PaperTrader:
    """Manages simulated paper trading positions"""
    
    def __init__(self, db_path: str = 'trades.db'):
        self.db_path = db_path
        self.positions: Dict[int, dict] = {}  # alert_id -> position data
        self._load_open_positions()
    
    def _load_open_positions(self):
        """Load open paper positions from database on startup"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM alerts 
                WHERE mode = 'paper' AND status = 'open'
            """)
            
            rows = cursor.fetchall()
            for row in rows:
                self.positions[row['id']] = {
                    'symbol': row['symbol'],
                    'side': row['side'],
                    'entry': row['entry'],
                    'sl': row['sl'],
                    'tp': row['tp'],
                    'size': row['size'],
                    'open_time': row['created_at'],
                    'rr_ratio': row['rr_ratio']
                }
            
            conn.close()
            logger.info(f"Loaded {len(self.positions)} open paper positions")
            
        except Exception as e:
            logger.error(f"Failed to load open positions: {e}")
    
    def open_position(self, alert_id: int, symbol: str, side: str, 
                     entry: float, sl: float, tp: float, size: float, 
                     rr_ratio: float) -> bool:
        """
        Simulate opening a new position.
        
        Returns:
            bool: True if position opened successfully
        """
        try:
            self.positions[alert_id] = {
                'symbol': symbol,
                'side': side.lower(),
                'entry': entry,
                'sl': sl,
                'tp': tp,
                'size': size,
                'open_time': datetime.utcnow().isoformat(),
                'rr_ratio': rr_ratio
            }
            
            logger.info(f"📝 Paper position opened: #{alert_id} {symbol} {side.upper()} @ {entry}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to open paper position #{alert_id}: {e}")
            return False
    
    def check_position(self, alert_id: int, current_price: float) -> Optional[Tuple[str, float]]:
        """
        Check if a position should be closed based on current price.
        
        Args:
            alert_id: Alert/position ID
            current_price: Current market price
            
        Returns:
            Tuple of (outcome, close_price) if position should close, None otherwise
            outcome: 'win', 'loss', or 'breakeven'
        """
        if alert_id not in self.positions:
            return None
        
        pos = self.positions[alert_id]
        side = pos['side']
        sl = pos['sl']
        tp = pos['tp']
        entry = pos['entry']
        
        # Check if SL or TP hit
        if side == 'buy':
            # Long position
            if current_price <= sl:
                return ('loss', sl)
            elif current_price >= tp:
                return ('win', tp)
        else:
            # Short position
            if current_price >= sl:
                return ('loss', sl)
            elif current_price <= tp:
                return ('win', tp)
        
        return None
    
    def close_position(self, alert_id: int, close_price: float, 
                      outcome: str, notes: str = '') -> Optional[float]:
        """
        Close a paper position and calculate P&L.
        
        Args:
            alert_id: Alert/position ID
            close_price: Price at which position closed
            outcome: 'win', 'loss', or 'breakeven'
            notes: Optional notes (e.g., 'TP hit', 'SL hit', 'Manual close')
            
        Returns:
            Simulated P&L in dollars, or None if position not found
        """
        if alert_id not in self.positions:
            logger.warning(f"Position #{alert_id} not found")
            return None
        
        pos = self.positions[alert_id]
        
        # Calculate P&L
        pnl = self._calculate_pnl(pos, close_price)
        
        # Update database
        self._update_database(alert_id, close_price, outcome, pnl, notes)
        
        # Remove from active positions
        del self.positions[alert_id]
        
        emoji = "✅" if outcome == 'win' else "❌"
        logger.info(f"{emoji} Paper position closed: #{alert_id} {pos['symbol']} {outcome.upper()} | P&L: ${pnl:.2f}")
        
        return pnl
    
    def _calculate_pnl(self, position: dict, close_price: float) -> float:
        """
        Calculate simulated P&L for a position.
        
        Simplified calculation assuming $10/pip for major pairs and $1/pip for Gold.
        """
        entry = position['entry']
        side = position['side']
        symbol = position['symbol'].upper()
        
        # Determine pip size
        if 'JPY' in symbol:
            pip_size = 0.01
            pip_value = 1000  # $10 per pip for standard lot
        elif 'XAU' in symbol or 'GOLD' in symbol:
            pip_size = 0.1
            pip_value = 1  # $1 per 0.1 move
        else:
            pip_size = 0.0001
            pip_value = 10  # $10 per pip for standard lot
        
        # Calculate pips
        if side == 'buy':
            pips = (close_price - entry) / pip_size
        else:
            pips = (entry - close_price) / pip_size
        
        # Calculate P&L (simplified, doesn't account for actual lot size)
        # Using position['size'] as multiplier
        pnl = pips * pip_value * position['size']
        
        return round(pnl, 2)
    
    def _update_database(self, alert_id: int, close_price: float, 
                        outcome: str, pnl: float, notes: str):
        """Update database with closed position data"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE alerts
                SET status = 'closed',
                    outcome = ?,
                    simulated_pnl = ?,
                    close_price = ?,
                    close_time = ?,
                    notes = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (outcome, pnl, close_price, datetime.utcnow().isoformat(), notes, alert_id))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            logger.error(f"Failed to update database for position #{alert_id}: {e}")
    
    def get_open_positions(self) -> Dict[int, dict]:
        """Get all currently open paper positions"""
        return self.positions.copy()
    
    def get_total_pnl(self) -> float:
        """Calculate total P&L from all closed paper positions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT SUM(simulated_pnl) FROM alerts 
                WHERE mode = 'paper' AND simulated_pnl IS NOT NULL
            """)
            
            result = cursor.fetchone()[0]
            conn.close()
            
            return result or 0.0
            
        except Exception as e:
            logger.error(f"Failed to calculate total P&L: {e}")
            return 0.0
    
    def get_statistics(self) -> dict:
        """Get paper trading statistics"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Total trades
            cursor.execute("SELECT COUNT(*) FROM alerts WHERE mode = 'paper'")
            total = cursor.fetchone()[0]
            
            # Wins and losses
            cursor.execute("""
                SELECT outcome, COUNT(*) FROM alerts 
                WHERE mode = 'paper' AND outcome IS NOT NULL 
                GROUP BY outcome
            """)
            outcomes = dict(cursor.fetchall())
            
            wins = outcomes.get('win', 0)
            losses = outcomes.get('loss', 0)
            total_closed = wins + losses
            
            # Win rate
            win_rate = (wins / total_closed * 100) if total_closed > 0 else 0
            
            # Total P&L
            total_pnl = self.get_total_pnl()
            
            conn.close()
            
            return {
                'total_trades': total,
                'open_positions': len(self.positions),
                'closed_trades': total_closed,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate statistics: {e}")
            return {}


# Singleton instance
_paper_trader_instance = None

def get_paper_trader(db_path: str = 'trades.db') -> PaperTrader:
    """Get or create the paper trader singleton instance"""
    global _paper_trader_instance
    if _paper_trader_instance is None:
        _paper_trader_instance = PaperTrader(db_path)
    return _paper_trader_instance
