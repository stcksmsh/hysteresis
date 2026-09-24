//! The literal mechanism behind `AudioClock`'s output-latency compensation:
//! a fixed-capacity ring buffer that delays what's written to the output
//! device by a configurable number of frames, while the caller can inspect
//! (and run analysis against) the undelayed input immediately. Interleaved
//! `f32` samples, any channel count.

pub struct DelayLine {
    channels: usize,
    capacity_frames: usize,
    buffer: Vec<f32>, // interleaved, capacity_frames * channels
    write_frame: u64, // monotonic frame counter, never wraps in practice
    delay_frames: usize,
}

impl DelayLine {
    /// `capacity_frames` is the maximum delay this instance can ever apply —
    /// fixed at construction so the audio callback never reallocates.
    pub fn new(channels: usize, capacity_frames: usize) -> Self {
        Self {
            channels,
            capacity_frames,
            buffer: vec![0.0; capacity_frames * channels],
            write_frame: 0,
            delay_frames: 0,
        }
    }

    /// Clamped to `[0, capacity_frames]` — silently caps rather than
    /// erroring, since a caller asking for more delay than was provisioned
    /// is a configuration mistake best made visible as "less delay than
    /// asked for" rather than a panic mid-stream.
    pub fn set_delay_frames(&mut self, frames: usize) {
        self.delay_frames = frames.min(self.capacity_frames);
    }

    pub fn delay_frames(&self) -> usize {
        self.delay_frames
    }

    /// `input`/`output` are both interleaved, length `frames * channels`.
    /// May alias-free overlap in the trivial case (delay 0); never aliases
    /// otherwise since output is written from buffer contents, not input
    /// directly, once delay > 0.
    pub fn process(&mut self, input: &[f32], output: &mut [f32]) {
        let channels = self.channels;
        assert_eq!(input.len() % channels, 0);
        assert_eq!(input.len(), output.len());
        let frames = input.len() / channels;

        for f in 0..frames {
            let write_slot = (self.write_frame as usize) % self.capacity_frames;
            for c in 0..channels {
                self.buffer[write_slot * channels + c] = input[f * channels + c];
            }

            // The frame `delay_frames` behind the one we just wrote — silence
            // until enough frames have ever been written (start-of-playback
            // ramp-in, not a wraparound read of stale/uninitialized data).
            let read_frame_index = self.write_frame as i64 - self.delay_frames as i64;
            if read_frame_index < 0 {
                for c in 0..channels {
                    output[f * channels + c] = 0.0;
                }
            } else {
                let read_slot = (read_frame_index as usize) % self.capacity_frames;
                for c in 0..channels {
                    output[f * channels + c] = self.buffer[read_slot * channels + c];
                }
            }

            self.write_frame += 1;
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_delay_passes_through_immediately() {
        let mut line = DelayLine::new(1, 8);
        line.set_delay_frames(0);
        let input = [1.0, 2.0, 3.0];
        let mut output = [0.0; 3];
        line.process(&input, &mut output);
        assert_eq!(output, input);
    }

    #[test]
    fn nonzero_delay_holds_back_and_then_reproduces_input() {
        let mut line = DelayLine::new(1, 8);
        line.set_delay_frames(3);

        let input = [10.0, 20.0, 30.0, 40.0, 50.0];
        let mut output = [0.0; 5];
        line.process(&input, &mut output);

        // First 3 frames of output are silence (nothing old enough yet).
        assert_eq!(&output[0..3], &[0.0, 0.0, 0.0]);
        // Frame 3 of output = frame 0 of input (delayed by 3), frame 4 = frame 1.
        assert_eq!(&output[3..5], &[10.0, 20.0]);
    }

    #[test]
    fn delay_survives_across_multiple_process_calls() {
        let mut line = DelayLine::new(1, 8);
        line.set_delay_frames(2);

        let mut out1 = [0.0; 4];
        line.process(&[1.0, 2.0, 3.0, 4.0], &mut out1);
        assert_eq!(out1, [0.0, 0.0, 1.0, 2.0]);

        let mut out2 = [0.0; 4];
        line.process(&[5.0, 6.0, 7.0, 8.0], &mut out2);
        assert_eq!(out2, [3.0, 4.0, 5.0, 6.0]);
    }

    #[test]
    fn stereo_channels_stay_independent() {
        let mut line = DelayLine::new(2, 4);
        line.set_delay_frames(1);
        // frame0 = (L=1,R=-1), frame1 = (L=2,R=-2)
        let input = [1.0, -1.0, 2.0, -2.0];
        let mut output = [0.0; 4];
        line.process(&input, &mut output);
        assert_eq!(output, [0.0, 0.0, 1.0, -1.0]);
    }

    #[test]
    fn requesting_more_delay_than_capacity_is_clamped_not_panicking() {
        let mut line = DelayLine::new(1, 4);
        line.set_delay_frames(100);
        assert_eq!(line.delay_frames(), 4);
    }
}
