"""Download a pinned MIMEX snapshot with Hugging Face Datasets and save locally."""
import argparse
import json
from pathlib import Path
from datasets import load_dataset, load_from_disk
from huggingface_hub import HfApi


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',default='data/mimex')
    args=parser.parse_args()
    root=Path(args.output).resolve()
    destination=root/'dataset'
    if destination.exists():
        raise SystemExit('Dataset destination already exists; leaving it unchanged.')
    root.mkdir(parents=True,exist_ok=True)
    info=HfApi().dataset_info('Anilot/MIMEX')
    revision=info.sha
    print('Downloading Anilot/MIMEX revision',revision,flush=True)
    dataset=load_dataset('Anilot/MIMEX',revision=revision,cache_dir=str(root/'cache'))
    dataset.save_to_disk(str(destination))
    reloaded=load_from_disk(str(destination))
    summary={'source':'https://huggingface.co/datasets/Anilot/MIMEX','revision':revision,
             'splits':{k:len(v) for k,v in reloaded.items()},
             'features':{k:v.features.to_dict() for k,v in reloaded.items()},
             'training_started':False}
    (root/'download.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'saved_to':str(destination),'revision':revision,'splits':summary['splits']},indent=2),flush=True)


if __name__=='__main__': main()
