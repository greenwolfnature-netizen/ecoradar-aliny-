# EcoRadar Indicator Library

Status: `definition_only`

The central indicator library is implemented in
`ecoradar/indicators/library.py`.

It stores the static definition of each EcoRadar indicator:

- name
- code
- thematic block
- objective
- required data
- data sources
- calculation method
- 0-100 valuation scale
- confidence guidance
- limitations
- associated recommendations

It does not calculate indicator values. Calculation belongs to the future
Analysis Engine after the required source connectors have produced verified
inputs.

## Current Coverage

- `ECO_COB_01` to `ECO_COB_05`
- `ECO_HAB_01` to `ECO_HAB_05`
- `ECO_VEG_01` to `ECO_VEG_05`
- `ECO_CLIM_01` to `ECO_CLIM_05`
- `ECO_FAU_01` to `ECO_FAU_05`
- `ECO_ANT_01` to `ECO_ANT_06`
- `ECO_INC_01` to `ECO_INC_05`
- `ECO_AIG_01` to `ECO_AIG_05`
- `ECO_CON_01` to `ECO_CON_04`
- `ECO_CAMP_01` to `ECO_CAMP_03`

Total: 48 indicators.

## Usage

```python
from ecoradar.indicators import get_indicator, list_indicators

indicator = get_indicator("ECO_COB_01")
all_definitions = list_indicators()
```

All definitions currently have `calculation_status = "not_implemented"`.
