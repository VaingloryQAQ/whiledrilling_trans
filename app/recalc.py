# app/recalc.py
import json
from sqlmodel import Session, select, create_engine
from .ingest import DB_PATH
from .models import Image, anomalies_to_str
from .parser import parse_metadata
from .classifier import classify
from .config import load_rules

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def main():
    rules = load_rules()
    updated = 0
    with Session(engine) as sess:
        rows = sess.exec(select(Image)).all()
        for img in rows:
            meta = parse_metadata(img.file_path)
            img.well_name = meta["well_name"]
            img.sample_type = meta["sample_type"]
            img.start_depth = meta["start_depth"]
            img.end_depth = meta["end_depth"]
            img.ndepth_center = (
                (img.start_depth + img.end_depth) / 2
                if img.start_depth is not None and img.end_depth is not None else None
            )
            cat, explain = classify(img.file_path, img.sample_type, rules)
            img.category = cat
            # 合并异常（如果分类仍未命中就标注）
            anomalies = meta["anomalies"][:]
            if not cat:
                anomalies.append("缺少类别")
            img.anomalies = anomalies_to_str(anomalies)
            img.explain = json.dumps(explain, ensure_ascii=False)
            sess.add(img)
            updated += 1
            if updated % 500 == 0:
                sess.commit()
        sess.commit()
    print(f"recalc done: {updated} rows")

if __name__ == "__main__":
    main()
