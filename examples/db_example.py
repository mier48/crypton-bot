from src.config.database import SessionLocal
from src.utils.database_manager import DatabaseManager, init_db

# Initialize the database
init_db()

# Create a database session
db = SessionLocal()
try:
    # Create a database manager
    db_manager = DatabaseManager(db)
    
    # Example: Add a new asset (sin especificar total_purchase_price)
    new_asset = db_manager.add_asset(
        symbol="BTCUSDT",
        amount=0.1,
        purchase_price=50000.0,  # 50,000 USDT por BTC
        is_bubble=False,
        force_sell=False
    )
    print(f"Added new asset: {new_asset}")
    
    # Example: Add another asset (especificando manualmente el total)
    new_asset2 = db_manager.add_asset(
        symbol="ETHUSDT",
        amount=2.0,
        purchase_price=3000.0,  # 3,000 USDT por ETH
        total_purchase_price=5500.0,  # Podemos especificarlo manualmente si es diferente
        is_bubble=False,
        force_sell=False
    )
    print(f"Added second asset: {new_asset2}")
    
    # Example: Get all assets
    print("\nAll assets:")
    assets = db_manager.get_assets()
    for asset in assets:
        print(f"- {asset.symbol}: {asset.amount} @ ${asset.purchase_price} = ${asset.total_purchase_price}")
    
    # Example: Update an asset (cambiar cantidad y ver cómo se actualiza el total)
    if assets:
        updated = db_manager.update_asset(
            asset_id=assets[0].id,
            amount=0.15,  # Cambiar la cantidad
            is_bubble=True,
            current_price=52000.0
        )
        print(f"\nUpdated asset (cambiada cantidad): {updated}")
        
    # Verificar que el total se actualizó correctamente
    updated_asset = db_manager.get_asset(assets[0].id)
    print(f"Verificación - Total actualizado: {updated_asset.amount} * {updated_asset.purchase_price} = {updated_asset.total_purchase_price}")
    
    # Example: Get assets marked as bubbles
    print("\nBubble assets:")
    bubble_assets = db_manager.get_bubble_assets()
    for asset in bubble_assets:
        print(f"- {asset.symbol}: {asset.amount} @ ${asset.purchase_price}")
        
finally:
    # Close the session
    db.close()
