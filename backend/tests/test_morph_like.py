from database import engine
from sqlmodel import Session, select
from models import Morphology
with Session(engine) as session:
    res = session.exec(select(Morphology).where(Morphology.lemma.like("%بلا%"))).all()
    roots = set([r.root for r in res if r.root])
    lemmas = set([r.lemma for r in res])
    print("Roots found for %بلا%:", roots)
    print("Lemmas found for %بلا%:", list(lemmas)[:10])
