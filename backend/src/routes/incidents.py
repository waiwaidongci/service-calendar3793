from fastapi import APIRouter,Depends,HTTPException
from src.config.database import database
from src.controllers.auth import current,admin
from src.models.incident import IncidentBook
from src.schemas.requests import ApplyInput
from src.services import incident
router=APIRouter()
@router.get('/incident-books')
def books(db=Depends(database),u=Depends(current)): return incident.list_books(db)
@router.get('/incident-books/{id}')
def book(id:int,db=Depends(database),u=Depends(current)):
 obj=db.get(IncidentBook,id)
 if not obj: raise HTTPException(404,'事故簿不存在')
 return incident.detail(db,obj)
@router.get('/incident-books/{id}/numbers/{number}')
def history(id:int,number:str,db=Depends(database),u=Depends(current)):
 if not db.get(IncidentBook,id): raise HTTPException(404,'事故簿不存在')
 return incident.number_history(db,id,number)
@router.post('/incident-books/apply')
def apply(b:ApplyInput,db=Depends(database),u=Depends(admin)): return incident.apply_report(db,u,b.report_id,b.base_version)
