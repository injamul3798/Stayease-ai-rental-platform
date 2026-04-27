from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from redis import Redis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from api.dependencies import db_session_dependency, redis_dependency
from api.schema import ChatMessageRequest, ChatMessageResponse, ConversationHistoryResponse
from services.chat_service import ChatService
from services.history_service import ConversationNotFoundError, HistoryStoreError


router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/{conversation_id}/message", response_model=ChatMessageResponse)
def send_message(
    conversation_id: str,
    payload: ChatMessageRequest,
    session: Session = Depends(db_session_dependency),
    redis_client: Redis = Depends(redis_dependency),
) -> ChatMessageResponse:
    """Send a guest message to the StayEase chat agent."""
    service = ChatService(session=session, redis_client=redis_client)
    try:
        return service.handle_message(conversation_id=conversation_id, payload=payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    except HistoryStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="database operation failed") from error
    except RuntimeError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error


@router.get("/{conversation_id}/history", response_model=ConversationHistoryResponse)
def get_history(
    conversation_id: str,
    session: Session = Depends(db_session_dependency),
    redis_client: Redis = Depends(redis_dependency),
) -> ConversationHistoryResponse:
    """Return the ordered history for one conversation."""
    service = ChatService(session=session, redis_client=redis_client)
    try:
        return service.get_history(conversation_id=conversation_id)
    except ConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except HistoryStoreError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    except SQLAlchemyError as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="database operation failed") from error
