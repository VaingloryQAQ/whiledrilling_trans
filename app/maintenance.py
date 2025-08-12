# app/maintenance.py
from sqlmodel import Session, select
from .db import get_engine
from .models import Image
from .normalizer import Normalizer

def cleanup_db():
    with Session(get_engine()) as sess:
        rows = sess.exec(select(Image)).all()
        changed = 0
        for r in rows:
            st, rej_a = Normalizer.canon_sample_type_full(r.sample_type, r.rel_path)
            cat, rej_b = Normalizer.canon_category(r.category, r.rel_path)
            if rej_a or rej_b:
                sess.delete(r)
                changed += 1
                continue
            new = False
            if st != r.sample_type:
                r.sample_type = st; new = True
            if cat != r.category:
                r.category = cat; new = True
            if new:
                sess.add(r); changed += 1
        sess.commit()
        print(f"[cleanup] changed/deleted: {changed}")
