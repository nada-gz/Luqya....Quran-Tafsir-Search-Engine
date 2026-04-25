from database import engine
from sqlmodel import Session, select
from models import Morphology
with Session(engine) as session:
    morph = session.exec(select(Morphology).limit(1)).first()
    print("Morphology cols:", dir(morph))
    print("Sample:", morph.text, morph.lemma, morph.root)
