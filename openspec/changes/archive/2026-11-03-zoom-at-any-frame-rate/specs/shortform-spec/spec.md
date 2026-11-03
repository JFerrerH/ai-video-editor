## ADDED Requirements

### Requirement: Zoomed segments keep their length at any frame rate

A segment with a zoom SHALL last as long as its audio whatever the source's frame rate. A still inside it SHALL always find its frame. A frame that can't be made SHALL be an error naming the output time and the segment.

#### Scenario: A 24 fps take with a punch-in

- **WHEN** a 24 fps take has a 2.5 s segment with a punch zoom
- **THEN** the segment renders 2.5 s of video at 30 fps, and a still 0.05 s before its end exists
