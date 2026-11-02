## ADDED Requirements

### Requirement: Head box

The face step SHALL return, next to each source's face centre, the head box it measures: `head: [x0, y0, x1, y1]` in source pixels, the median over the sampled frames of the top 30% band of the person matte. When the face is `null`, the head box SHALL also be `null`. It SHALL be deterministic for the same file and backend.

#### Scenario: Seated speaker

- **WHEN** the face step runs on a vertical take of one seated speaker
- **THEN** its JSON has `head` with x0 < face x < x1 and y0 < face y < y1, and a still at mid-take shows the head inside that box
