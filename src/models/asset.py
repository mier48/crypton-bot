from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declared_attr
from src.config.database import Base, SQLALCHEMY_DATABASE_URL
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlite3 import Connection as SQLite3Connection

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Crear un motor específico para las migraciones
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = {
        'extend_existing': True,  # Permite redefinir la tabla si ya existe
        'sqlite_autoincrement': True
    }

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, unique=True)  # Añadido unique=True
    purchase_price = Column(Float, nullable=False)  # Precio por unidad
    amount = Column(Float, nullable=False)
    total_purchase_price = Column(Float, nullable=False)  # Precio total de la compra (cantidad * precio unitario)
    is_bubble = Column(Boolean, default=False)
    force_sell = Column(Boolean, default=False)
    purchase_date = Column(DateTime(timezone=True), server_default=func.now())
    last_updated = Column(DateTime(timezone=True), onupdate=func.now())

    def __init__(self, **kwargs):
        # Calcular el precio total de la compra si no se proporciona
        if 'total_purchase_price' not in kwargs and 'amount' in kwargs and 'purchase_price' in kwargs:
            kwargs['total_purchase_price'] = kwargs['amount'] * kwargs['purchase_price']
        super().__init__(**kwargs)

    def __repr__(self):
        return (
            f"<Asset(symbol='{self.symbol}', "
            f"amount={self.amount}, "
            f"purchase_price={self.purchase_price}, "
            f"total_purchase_price={self.total_purchase_price})>"
        )
