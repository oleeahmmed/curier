# Manual migration to remove old bag fields

from django.db import migrations


def remove_old_columns(apps, schema_editor):
    """Manually remove old columns from bag table"""
    with schema_editor.connection.cursor() as cursor:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(exportimport_bag)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'total_parcels' in columns or 'total_weight' in columns:
            # SQLite doesn't support DROP COLUMN directly, so we need to recreate the table
            cursor.execute("""
                CREATE TABLE exportimport_bag_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bag_number varchar(50) NOT NULL UNIQUE,
                    status varchar(20) NOT NULL,
                    sealed_at datetime NULL,
                    created_at datetime NOT NULL,
                    sealed_by_id INTEGER NULL,
                    shipment_id bigint NULL UNIQUE,
                    weight decimal NOT NULL,
                    FOREIGN KEY (sealed_by_id) REFERENCES auth_user(id),
                    FOREIGN KEY (shipment_id) REFERENCES exportimport_shipment(id)
                )
            """)
            
            # Copy data from old table to new table
            cursor.execute("""
                INSERT INTO exportimport_bag_new 
                (id, bag_number, status, sealed_at, created_at, sealed_by_id, shipment_id, weight)
                SELECT id, bag_number, status, sealed_at, created_at, sealed_by_id, shipment_id, weight
                FROM exportimport_bag
            """)
            
            # Drop old table
            cursor.execute("DROP TABLE exportimport_bag")
            
            # Rename new table
            cursor.execute("ALTER TABLE exportimport_bag_new RENAME TO exportimport_bag")
            
            # Recreate indexes
            cursor.execute("CREATE UNIQUE INDEX exportimport_bag_bag_number_unique ON exportimport_bag(bag_number)")
            cursor.execute("CREATE UNIQUE INDEX exportimport_bag_shipment_id_unique ON exportimport_bag(shipment_id)")
            cursor.execute("CREATE INDEX exportimport_bag_sealed_by_id ON exportimport_bag(sealed_by_id)")


class Migration(migrations.Migration):

    dependencies = [
        ('exportimport', '0007_remove_bag_shipments_remove_bag_total_parcels_and_more'),
    ]

    operations = [
        migrations.RunPython(remove_old_columns, migrations.RunPython.noop),
    ]
