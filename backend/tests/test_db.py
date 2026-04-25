from database import engine
from sqlmodel import Session
from models import Morphology
with Session(engine) as session:
    morph = session.query(Morphology).filter(Morphology.root == 'بلو').first()
    print("Found morph root!" if morph else "Not found")
