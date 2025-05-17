from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from ..models.asset import Asset

def init_db():
    """Initialize the database by creating all tables"""
    from ..config.database import Base, engine
    Base.metadata.create_all(bind=engine)

class DatabaseManager:
    def __init__(self, db: Session):
        self.db = db

    def add_asset(
        self,
        symbol: str,
        amount: float,
        purchase_price: float,
        total_purchase_price: float = None,
        is_bubble: bool = False,
        force_sell: bool = False
    ) -> Asset:
        """Add a new asset to the database"""
        asset = Asset(
            symbol=symbol.upper(),
            amount=amount,
            purchase_price=purchase_price,
            total_purchase_price=total_purchase_price,  # Si es None, se calculará automáticamente
            is_bubble=is_bubble,
            force_sell=force_sell,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_asset(self, asset_id: int) -> Optional[Asset]:
        """Get an asset by ID"""
        return self.db.query(Asset).filter(Asset.id == asset_id).first()

    def get_assets(self, skip: int = 0, limit: int = 100) -> List[Asset]:
        """Get all assets with pagination"""
        return self.db.query(Asset).offset(skip).limit(limit).all()

    def get_asset_by_symbol(self, symbol: str) -> Optional[Asset]:
        """Get an asset by its symbol"""
        return self.db.query(Asset).filter(Asset.symbol == symbol.upper()).first()

    def update_asset(self, asset_id: int, **kwargs) -> Optional[Asset]:
        """Update asset fields"""
        asset = self.get_asset(asset_id)
        if not asset:
            return None
            
        # Si se actualiza amount o purchase_price, recalcular total_purchase_price
        if 'amount' in kwargs or 'purchase_price' in kwargs:
            new_amount = kwargs.get('amount', asset.amount)
            new_price = kwargs.get('purchase_price', asset.purchase_price)
            kwargs['total_purchase_price'] = new_amount * new_price
            
        for key, value in kwargs.items():
            if hasattr(asset, key):
                setattr(asset, key, value)
                
        asset.last_updated = datetime.utcnow()
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def delete_asset(self, asset_id: int) -> bool:
        """Delete an asset"""
        asset = self.get_asset(asset_id)
        if not asset:
            return False
            
        self.db.delete(asset)
        self.db.commit()
        return True
        
    def get_assets_for_sale(self) -> List[Asset]:
        """Get all assets marked for forced sale"""
        return self.db.query(Asset).filter(Asset.force_sell == True).all()
        
    def get_bubble_assets(self) -> List[Asset]:
        """Get all assets marked as potential bubbles"""
        return self.db.query(Asset).filter(Asset.is_bubble == True).all()
