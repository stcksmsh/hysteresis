//! Fixed-rate tick accounting, shared by any [`hyst_core::signal::VizOutput`] that must
//! run its own work at a cadence slower than (and decoupled from) the render frame rate.
//!
//! [`FieldOutput`](crate::field_output::FieldOutput) is the first consumer (dense physical
//! arrays refresh at ~15 Hz, not per-frame — see `SINTEZA_CHOREOGRAPHY.md` §5.3), but nothing
//! here is field-specific: a future servo/DMX output wanting its own throttle uses the same
//! type.

/// Converts irregular per-frame `dt` into a whole number of fixed-period ticks.
///
/// `VizOutput::update` is called once per render frame with that frame's `dt`; a physical
/// output that must not run faster than, say, 15 Hz feeds every `dt` through
/// [`TickAccumulator::advance`] and only does its own work that many times, carrying any
/// leftover fractional time forward rather than dropping it (so a long stall followed by a
/// big `dt` still fires the right number of ticks, not zero and not a burst averaged away).
#[derive(Debug, Clone, Copy)]
pub struct TickAccumulator {
    period: f32,
    accumulated: f32,
}

impl TickAccumulator {
    /// `hz` must be finite and positive.
    pub fn new(hz: f32) -> Self {
        assert!(
            hz.is_finite() && hz > 0.0,
            "TickAccumulator hz must be > 0, got {hz}"
        );
        Self {
            period: 1.0 / hz,
            accumulated: 0.0,
        }
    }

    /// The fixed duration of one tick, in seconds (`1.0 / hz`).
    pub fn period(&self) -> f32 {
        self.period
    }

    /// Feed elapsed wall/render time in; returns how many whole ticks are now due.
    /// Consumes exactly `ticks * period()` seconds of the accumulated time, keeping any
    /// remainder for the next call.
    pub fn advance(&mut self, dt: f32) -> u32 {
        self.accumulated += dt.max(0.0);
        // Nudge by a tiny epsilon before flooring so an accumulated time that is "one period"
        // up to f32 rounding error (e.g. 1.0 / (1.0 / 15.0) landing at 14.999999) still counts
        // as a full tick rather than silently dropping it.
        let ticks = (self.accumulated / self.period + 1e-4).floor();
        let ticks = if ticks.is_finite() && ticks > 0.0 {
            ticks as u32
        } else {
            0
        };
        self.accumulated -= ticks as f32 * self.period;
        ticks
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fires_one_tick_per_full_period() {
        let mut tick = TickAccumulator::new(15.0);
        let period = tick.period();
        assert!((period - 1.0 / 15.0).abs() < 1e-6);
        assert_eq!(tick.advance(period), 1);
        assert_eq!(tick.advance(period), 1);
    }

    #[test]
    fn carries_fractional_time_forward_instead_of_dropping_it() {
        let mut tick = TickAccumulator::new(10.0); // period = 0.1s
        assert_eq!(tick.advance(0.04), 0);
        assert_eq!(tick.advance(0.04), 0);
        // 0.08s accumulated so far; +0.03 crosses one period (0.1), 0.01 left over.
        assert_eq!(tick.advance(0.03), 1);
        // that leftover 0.01 plus another 0.09 crosses a second period.
        assert_eq!(tick.advance(0.09), 1);
    }

    #[test]
    fn a_long_stall_then_big_dt_fires_every_missed_tick_not_zero_and_not_unbounded() {
        let mut tick = TickAccumulator::new(15.0); // period ~0.0667s
        let ticks = tick.advance(1.0);
        assert_eq!(ticks, 15);
    }

    #[test]
    fn negative_dt_is_ignored_rather_than_going_backwards() {
        let mut tick = TickAccumulator::new(15.0);
        assert_eq!(tick.advance(-5.0), 0);
        assert_eq!(tick.advance(tick.period()), 1);
    }
}
