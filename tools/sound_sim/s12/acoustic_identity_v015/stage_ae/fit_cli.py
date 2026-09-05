from __future__ import annotations
import argparse
from pathlib import Path
from .parameter_fit import run_family_fit
from .vehicle_profiles import VEHICLES


def main(argv=None)->int:
    p=argparse.ArgumentParser(description="Stage AE canonical diagnostic family fit")
    p.add_argument("--vehicle",choices=list(VEHICLES),required=True); p.add_argument("--caseset-json",type=Path,required=True); p.add_argument("--family",choices=["body","path","induction","afterfire"],required=True); p.add_argument("--output-root",type=Path,required=True); p.add_argument("--samples",type=int,default=16); p.add_argument("--seed",type=int,default=20260905); p.add_argument("--base-config-json",type=Path)
    a=p.parse_args(argv); receipt=run_family_fit(a.vehicle,a.caseset_json,a.family,a.output_root,a.samples,a.seed,a.base_config_json); print(receipt); return 0

if __name__=="__main__": raise SystemExit(main())
