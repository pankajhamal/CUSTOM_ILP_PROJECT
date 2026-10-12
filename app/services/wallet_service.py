from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from app.core.config import settings
from app.models.user import User
from app.models.wallet import WalletAddress
from app.schemas.wallet import WalletAddressCreate, WalletAddressRead
from app.services.rafiki_client import ( RafikiClient, RafikiClientError)


logger = logging.getLogger(__name__)


async def create_wallet_address(
 *,
 payload: WalletAddressCreate,
 session: AsyncSession,
 rafiki: RafikiClient,       
) -> WalletAddressRead:

    #Find the User
    user = await session.get(User, payload.user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    #Get the required assetID
    asset_id = settings.RAFIKI_ASSET_ID
    base_url = settings.WALLET_ADDRESS_BASE_URL.rstrip("/")
    address = f"{base_url}/{user.id}"
    asset_code = settings.RAFIKI_ASSET_CODE
    asset_scale = settings.RAFIKI_ASSET_SCALE

    if not asset_id:
        raise HTTPException(
            status_code=500,
            details="Default Rafiki asset_id is not configured"
        )

    #Create wallet address through Rafiki 
    try:
        result = await rafiki.create_wallet_address(
            asset_id=asset_id,
            address=address,
            public_name=str(user.username)
        )
    except RafikiClientError as exc:
        logger.exception("Rafiki wallet creation failed")
        raise HTTPException(
            status_code=502,
            detail=str(exc),
        ) from exc

    # Presist the return wallet address information 

    wallet = WalletAddress(
        user_id=user.id,
        wallet_address=address,
        rafiki_wallet_address_id=result["id"],
        asset_code=asset_code,
        asset_scale=str(asset_scale),
    )

    session.add(wallet)

    try:
        await session.commit()
        await session.refresh(wallet)
    except Exception:
        await session.rollback()
        raise

    return wallet


    