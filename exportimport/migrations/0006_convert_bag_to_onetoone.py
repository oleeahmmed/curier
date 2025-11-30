# Generated manually

from django.db import migrations, models
import django.db.models.deletion


def check_and_remove_fields(apps, schema_editor):
    """Check if fields exist before removing"""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('exportimport', '0005_customer_country'),
    ]

    operations = [
        # Add OneToOne field first
        migrations.AddField(
            model_name='bag',
            name='shipment',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='bag',
                to='exportimport.shipment',
                help_text='One shipment per bag'
            ),
        ),
        # Add weight field
        migrations.AddField(
            model_name='bag',
            name='weight',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text='Bag weight in KG',
                max_digits=8
            ),
        ),
    ]
