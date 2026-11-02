## ADDED Requirements

### Requirement: Matte windows on the cut base

The matte step SHALL accept windows of the cut base (output seconds) and write one matte per window, so a `behind` event spanning two segments needs one matte. Windows SHALL be padded 0.1 s before and after, and SHALL be merged when they touch.

#### Scenario: Two behind events close together

- **WHEN** `behind` events run 22.25–24.30 and 24.35–25.00
- **THEN** one matte covering 22.15–25.10 is written
