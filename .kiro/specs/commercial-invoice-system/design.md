# Design Document: Commercial Invoice System

## Overview

The Commercial Invoice System extends the existing Django-based shipment management application to support a single invoice file per shipment. The system provides two invoice management approaches: uploading pre-existing invoice documents (PDF/image) or generating invoices with product line items. The design emphasizes simplicity with a single FileField on the Shipment model, template-based permission enforcement, and temporary product line item handling during PDF generation.

### Key Design Principles

1. **Single Invoice Per Shipment**: Only one invoice can exist at a time; replacement requires deletion first
2. **No Separate Models**: Invoice is a FileField on the existing Shipment model; no CommercialInvoice or InvoiceItem models
3. **Temporary Line Items**: Product line items exist only during PDF generation and are not persisted
4. **Template-Level Permissions**: All permission checks occur in Django templates using conditional logic
5. **AWB Prerequisite**: Invoice generation requires an assigned AWB number (shipment must be BOOKED or later)
6. **Staff Override Capability**: Staff can edit shipper/consignee information for PDF generation without updating the shipment database

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Django Application                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐      ┌──────────────┐      ┌───────────┐ │
│  │   Templates  │◄─────┤    Views     │◄─────┤   Forms   │ │
│  │  (Shipment   │      │  (Invoice    │      │ (Invoice  │ │
│  │   Detail)    │      │   Upload,    │      │  Upload,  │ │
│  │              │      │   Generate,  │      │  Generate)│ │
│  │              │      │   Delete)    │      │           │ │
│  └──────────────┘      └──────┬───────┘      └───────────┘ │
│                               │                              │
│                               ▼                              │
│                      ┌─────────────────┐                     │
│                      │  Shipment Model │                     │
│                      │  (invoice field)│                     │
│                      └─────────────────┘                     │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           PDF Generation Service                      │   │
│  │  - ReportLab library                                  │   │
│  │  - Temporary line item processing                     │   │
│  │  - Shipper/consignee override handling                │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   File Storage       │
                    │   (Django Media)     │
                    └──────────────────────┘
```

### Request Flow

**Invoice Upload Flow:**
```
User → Shipment Detail Page → Upload Form → View validates file → 
Save to Shipment.invoice → Redirect to Shipment Detail
```

**Invoice Generation Flow:**
```
Staff → Shipment Detail Page → "Create Invoice" Button → 
Generation Form (pre-populated) → Staff adds line items → 
Submit → PDF Generation Service → Save PDF to Shipment.invoice → 
Redirect to Shipment Detail
```

**Invoice Deletion Flow:**
```
User → Shipment Detail Page → Delete Button → Confirmation → 
View deletes file → Clear Shipment.invoice → Redirect to Shipment Detail
```

## Components and Interfaces

### Database Schema

#### Modified Shipment Model

The existing `Shipment` model will be extended with a single field:

```python
class Shipment(models.Model):
    # ... existing fields ...
    
    # New field for commercial invoice
    invoice = models.FileField(
        upload_to='invoices/%Y/%m/',
        blank=True,
        null=True,
        help_text="Commercial invoice document (PDF or image)"
    )
```

**Field Specifications:**
- `upload_to`: Organizes files by year/month for better file management
- `blank=True, null=True`: Invoice is optional
- Supported formats: PDF, JPG, JPEG, PNG (validated in form)
- Maximum file size: 10MB (validated in form)

**No Additional Models Required:**
- Product line items are NOT persisted in the database
- Line items are captured in the generation form and used immediately for PDF creation
- Shipper/consignee overrides are NOT stored; they only affect the generated PDF

### Forms

#### InvoiceUploadForm

```python
class InvoiceUploadForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = ['invoice']
    
    def clean_invoice(self):
        invoice = self.cleaned_data.get('invoice')
        
        if invoice:
            # Validate file extension
            ext = invoice.name.split('.')[-1].lower()
            if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
                raise ValidationError('Only PDF and image files are allowed')
            
            # Validate file size (10MB max)
            if invoice.size > 10 * 1024 * 1024:
                raise ValidationError('File size must not exceed 10MB')
        
        return invoice
```

#### InvoiceGenerationForm

This form captures temporary data for PDF generation:

```python
class InvoiceGenerationForm(forms.Form):
    # Shipper information (editable, pre-populated from shipment)
    shipper_name = forms.CharField(max_length=200, required=True)
    shipper_address = forms.CharField(widget=forms.Textarea, required=True)
    
    # Consignee information (editable, pre-populated from shipment)
    consignee_name = forms.CharField(max_length=200, required=True)
    consignee_address = forms.CharField(widget=forms.Textarea, required=True)
    
    # AWB (read-only, populated from shipment)
    awb_number = forms.CharField(max_length=50, disabled=True, required=False)
    
    # Product line items (dynamic formset)
    # Handled via JavaScript on frontend for dynamic add/remove
    
    def __init__(self, shipment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate from shipment
        self.fields['shipper_name'].initial = shipment.shipper_name
        self.fields['shipper_address'].initial = shipment.shipper_address
        self.fields['consignee_name'].initial = shipment.recipient_name
        self.fields['consignee_address'].initial = shipment.recipient_address
        self.fields['awb_number'].initial = shipment.awb_number
```

#### ProductLineItemFormSet

```python
class ProductLineItemForm(forms.Form):
    description = forms.CharField(max_length=500, required=True)
    weight = forms.DecimalField(max_digits=6, decimal_places=2, min_value=0.01, required=True)
    quantity = forms.IntegerField(min_value=1, required=True)
    unit_value = forms.DecimalField(max_digits=10, decimal_places=2, min_value=0.01, required=True)

# Dynamic formset for multiple line items
ProductLineItemFormSet = forms.formset_factory(
    ProductLineItemForm,
    extra=1,
    min_num=1,
    validate_min=True
)
```

### Views

#### invoice_upload_view

```python
@login_required
def invoice_upload_view(request, shipment_id):
    """
    Handle invoice file upload for a shipment.
    Accessible by staff and customers.
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and shipment.customer.user != request.user:
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice already exists
    if shipment.invoice:
        messages.error(request, "An invoice already exists. Please delete it first.")
        return redirect('shipment_detail', shipment_id=shipment_id)
    
    if request.method == 'POST':
        form = InvoiceUploadForm(request.POST, request.FILES, instance=shipment)
        if form.is_valid():
            form.save()
            messages.success(request, "Invoice uploaded successfully")
            return redirect('shipment_detail', shipment_id=shipment_id)
    else:
        form = InvoiceUploadForm()
    
    return render(request, 'exportimport/invoice_upload.html', {
        'form': form,
        'shipment': shipment
    })
```

#### invoice_generate_view

```python
@login_required
def invoice_generate_view(request, shipment_id):
    """
    Handle invoice generation with product line items.
    Accessible by staff only.
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Staff-only access
    if not request.user.is_staff:
        return HttpResponseForbidden("Only staff can generate invoices")
    
    # Check if AWB exists
    if not shipment.awb_number:
        messages.error(request, "Cannot generate invoice: Shipment must be booked first")
        return redirect('shipment_detail', shipment_id=shipment_id)
    
    # Check if invoice already exists
    if shipment.invoice:
        messages.error(request, "An invoice already exists. Please delete it first.")
        return redirect('shipment_detail', shipment_id=shipment_id)
    
    if request.method == 'POST':
        form = InvoiceGenerationForm(shipment, request.POST)
        formset = ProductLineItemFormSet(request.POST)
        
        if form.is_valid() and formset.is_valid():
            # Extract data
            shipper_name = form.cleaned_data['shipper_name']
            shipper_address = form.cleaned_data['shipper_address']
            consignee_name = form.cleaned_data['consignee_name']
            consignee_address = form.cleaned_data['consignee_address']
            
            line_items = []
            for item_form in formset:
                if item_form.cleaned_data:
                    line_items.append(item_form.cleaned_data)
            
            # Generate PDF
            pdf_file = generate_invoice_pdf(
                shipment=shipment,
                shipper_name=shipper_name,
                shipper_address=shipper_address,
                consignee_name=consignee_name,
                consignee_address=consignee_address,
                line_items=line_items
            )
            
            # Save PDF to shipment
            shipment.invoice.save(
                f'invoice_{shipment.awb_number}.pdf',
                ContentFile(pdf_file.getvalue()),
                save=True
            )
            
            messages.success(request, "Invoice generated successfully")
            return redirect('shipment_detail', shipment_id=shipment_id)
    else:
        form = InvoiceGenerationForm(shipment)
        formset = ProductLineItemFormSet()
    
    return render(request, 'exportimport/invoice_generate.html', {
        'form': form,
        'formset': formset,
        'shipment': shipment
    })
```

#### invoice_delete_view

```python
@login_required
def invoice_delete_view(request, shipment_id):
    """
    Handle invoice deletion.
    Staff: always allowed
    Customer: only when shipment status is PENDING
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and shipment.customer.user != request.user:
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice exists
    if not shipment.invoice:
        messages.error(request, "No invoice to delete")
        return redirect('shipment_detail', shipment_id=shipment_id)
    
    # Permission check for customers
    if not request.user.is_staff and shipment.current_status != 'PENDING':
        messages.error(request, "You can only delete invoices for pending shipments")
        return redirect('shipment_detail', shipment_id=shipment_id)
    
    if request.method == 'POST':
        # Delete the file from storage
        shipment.invoice.delete(save=False)
        shipment.invoice = None
        shipment.save()
        
        messages.success(request, "Invoice deleted successfully")
        return redirect('shipment_detail', shipment_id=shipment_id)
    
    return render(request, 'exportimport/invoice_delete_confirm.html', {
        'shipment': shipment
    })
```

#### invoice_download_view

```python
@login_required
def invoice_download_view(request, shipment_id):
    """
    Serve invoice file for download.
    Staff: always allowed
    Customer: only when shipment status is BOOKED or later
    """
    shipment = get_object_or_404(Shipment, id=shipment_id)
    
    # Check if user has access to this shipment
    if not request.user.is_staff and shipment.customer.user != request.user:
        return HttpResponseForbidden("You don't have permission to access this shipment")
    
    # Check if invoice exists
    if not shipment.invoice:
        return HttpResponseNotFound("Invoice not found")
    
    # Permission check for customers
    if not request.user.is_staff and shipment.current_status == 'PENDING':
        return HttpResponseForbidden("Invoice not available for pending shipments")
    
    # Serve the file
    response = FileResponse(shipment.invoice.open('rb'))
    response['Content-Disposition'] = f'attachment; filename="{shipment.invoice.name}"'
    return response
```

### PDF Generation Service

#### generate_invoice_pdf Function

```python
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO

def generate_invoice_pdf(shipment, shipper_name, shipper_address, 
                         consignee_name, consignee_address, line_items):
    """
    Generate a commercial invoice PDF with product line items.
    
    Args:
        shipment: Shipment instance
        shipper_name: Override shipper name (from form)
        shipper_address: Override shipper address (from form)
        consignee_name: Override consignee name (from form)
        consignee_address: Override consignee address (from form)
        line_items: List of dicts with keys: description, weight, quantity, unit_value
    
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph("<b>COMMERCIAL INVOICE</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.3*inch))
    
    # AWB Number
    awb_text = Paragraph(f"<b>AWB Number:</b> {shipment.awb_number}", styles['Normal'])
    elements.append(awb_text)
    elements.append(Spacer(1, 0.2*inch))
    
    # Shipper and Consignee Information
    info_data = [
        ['Shipper', 'Consignee'],
        [shipper_name, consignee_name],
        [shipper_address, consignee_address]
    ]
    
    info_table = Table(info_data, colWidths=[3*inch, 3*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Product Line Items Table
    table_data = [['Description', 'Weight (kg)', 'Quantity', f'Unit Value ({shipment.declared_currency})', f'Total ({shipment.declared_currency})']]
    
    total_value = 0
    for item in line_items:
        line_total = item['quantity'] * item['unit_value']
        total_value += line_total
        
        table_data.append([
            item['description'],
            f"{item['weight']:.2f}",
            str(item['quantity']),
            f"{item['unit_value']:.2f}",
            f"{line_total:.2f}"
        ])
    
    # Add total row
    table_data.append(['', '', '', 'TOTAL:', f"{total_value:.2f}"])
    
    product_table = Table(table_data, colWidths=[2.5*inch, 1*inch, 1*inch, 1.2*inch, 1.2*inch])
    product_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
    ]))
    
    elements.append(product_table)
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer
```

## Data Models

### Shipment Model Extension

```python
# Add to existing Shipment model in exportimport/models.py

invoice = models.FileField(
    upload_to='invoices/%Y/%m/',
    blank=True,
    null=True,
    help_text="Commercial invoice document (PDF or image)"
)
```

### Migration

```python
# Generated migration file

from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('exportimport', 'XXXX_previous_migration'),
    ]

    operations = [
        migrations.AddField(
            model_name='shipment',
            name='invoice',
            field=models.FileField(
                blank=True,
                help_text='Commercial invoice document (PDF or image)',
                null=True,
                upload_to='invoices/%Y/%m/'
            ),
        ),
    ]
```

### Temporary Data Structures

Product line items are NOT stored in the database. They exist only as form data during the generation process:

```python
# Example line item structure (dict, not a model)
line_item = {
    'description': 'Electronics - Mobile Phone',
    'weight': 0.5,  # kg
    'quantity': 2,
    'unit_value': 150.00  # in shipment.declared_currency
}
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Upload File Validation

*For any* file upload attempt, the system should accept the file if and only if it is a PDF or image format (PDF, JPG, JPEG, PNG) and does not exceed 10MB in size.

**Validates: Requirements 1.1, 1.4**

### Property 2: Invoice Storage After Upload

*For any* valid file upload to a shipment without an existing invoice, the shipment's invoice field should contain the uploaded file after successful upload.

**Validates: Requirements 1.2**

### Property 3: Single Invoice Constraint

*For any* shipment with an existing invoice, attempts to upload or generate a new invoice should fail until the existing invoice is deleted.

**Validates: Requirements 1.8**

### Property 4: Customer Download Access by Status

*For any* shipment with an invoice where the user is a customer, download and preview buttons should be visible if and only if the shipment status is BOOKED or later (not PENDING).

**Validates: Requirements 2.2, 2.3**

### Property 5: Invoice File Download

*For any* shipment with an invoice, when an authorized user requests download, the system should serve the exact file stored in the invoice field.

**Validates: Requirements 2.4**

### Property 6: Staff Delete Access

*For any* shipment with an invoice where the user is staff, the delete button should be visible regardless of shipment status.

**Validates: Requirements 3.1**

### Property 7: Customer Delete Access by Status

*For any* shipment with an invoice where the user is a customer, the delete button should be visible if and only if the shipment status is PENDING.

**Validates: Requirements 3.3**

### Property 8: Invoice Deletion Cleanup

*For any* shipment with an invoice, after deletion, both the file should be removed from storage and the shipment's invoice field should be null.

**Validates: Requirements 3.4, 3.5**

### Property 9: Form Pre-population from Shipment

*For any* shipment, when the invoice generation form is initialized, the shipper name, shipper address, consignee name, consignee address, and AWB number fields should be pre-populated with the corresponding values from the shipment record.

**Validates: Requirements 4.4, 4.5, 4.6, 4.7, 4.15**

### Property 10: Shipper/Consignee Override Isolation

*For any* invoice generation with edited shipper or consignee fields, the generated PDF should contain the edited values, but the shipment record in the database should remain unchanged with its original values.

**Validates: Requirements 4.12, 4.13**

### Property 11: Multiple Line Items Support

*For any* invoice generation form submission with N product line items (where N ≥ 1), all N line items should be captured and included in the generated PDF.

**Validates: Requirements 4.17, 4.18**

### Property 12: PDF Generation and Storage

*For any* valid invoice generation form submission, the system should generate a PDF document and store it in the shipment's invoice field.

**Validates: Requirements 4.19, 4.20, 5.1**

### Property 13: Line Item Non-Persistence

*For any* invoice generation, after the PDF is created and stored, no product line item records should exist in the database.

**Validates: Requirements 4.21**

### Property 14: PDF Content Completeness

*For any* generated invoice PDF, the document should contain the shipper name and address, consignee name and address, AWB number, a table with columns for description/weight/quantity/value, and the currency from the shipment's declared_currency field.

**Validates: Requirements 5.2, 5.3, 5.4, 5.6, 5.7**

### Property 15: PDF Total Calculation

*For any* generated invoice PDF with line items, the displayed total value should equal the sum of (quantity × unit_value) for all line items.

**Validates: Requirements 5.5**

### Property 16: AWB Prerequisite Enforcement

*For any* shipment without an AWB number, invoice generation attempts should fail with an appropriate error.

**Validates: Requirements 6.2**

### Property 17: Line Item Field Validation

*For any* product line item in an invoice generation form, the system should reject the item if any of the required fields (description, weight, quantity, unit_value) are empty.

**Validates: Requirements 7.2**

### Property 18: Positive Numeric Validation

*For any* product line item, the system should reject the item if weight is not a positive number, quantity is not a positive integer, or unit_value is not a positive number.

**Validates: Requirements 7.3, 7.4, 7.5**

### Property 19: Validation Error Messaging

*For any* validation failure during invoice generation, the system should display error messages that specifically indicate which fields are invalid.

**Validates: Requirements 7.6**

## Error Handling

### File Upload Errors

**Invalid File Format:**
- Error Message: "Only PDF and image files (PDF, JPG, JPEG, PNG) are allowed"
- HTTP Status: 400 Bad Request
- User Action: Select a valid file format

**File Size Exceeded:**
- Error Message: "File size must not exceed 10MB"
- HTTP Status: 400 Bad Request
- User Action: Compress or select a smaller file

**Invoice Already Exists:**
- Error Message: "An invoice already exists. Please delete it first."
- HTTP Status: 400 Bad Request
- User Action: Delete existing invoice before uploading

**Storage Error:**
- Error Message: "Failed to save invoice file. Please try again."
- HTTP Status: 500 Internal Server Error
- User Action: Retry upload
- System Action: Log error details for debugging

### Invoice Generation Errors

**Missing AWB Number:**
- Error Message: "Cannot generate invoice: Shipment must be booked first"
- HTTP Status: 400 Bad Request
- User Action: Book the shipment to assign an AWB number

**No Line Items:**
- Error Message: "At least one product line item is required"
- HTTP Status: 400 Bad Request
- User Action: Add at least one line item

**Invalid Line Item Data:**
- Error Message: "Invalid line item: [field] must be [constraint]"
  - Examples: "weight must be a positive number", "quantity must be a positive integer"
- HTTP Status: 400 Bad Request
- User Action: Correct the invalid field values

**PDF Generation Failure:**
- Error Message: "Failed to generate invoice PDF. Please try again."
- HTTP Status: 500 Internal Server Error
- User Action: Retry generation
- System Action: Log error details including line item data

### Invoice Deletion Errors

**No Invoice to Delete:**
- Error Message: "No invoice to delete"
- HTTP Status: 400 Bad Request
- User Action: None required

**Permission Denied (Customer, Non-PENDING):**
- Error Message: "You can only delete invoices for pending shipments"
- HTTP Status: 403 Forbidden
- User Action: Contact staff for assistance

**File Deletion Failure:**
- Error Message: "Failed to delete invoice file. Please try again."
- HTTP Status: 500 Internal Server Error
- User Action: Retry deletion
- System Action: Log error details; may require manual cleanup

### Access Control Errors

**Unauthorized Shipment Access:**
- Error Message: "You don't have permission to access this shipment"
- HTTP Status: 403 Forbidden
- User Action: Verify shipment ownership or contact support

**Customer Generation Attempt:**
- Error Message: "Only staff can generate invoices"
- HTTP Status: 403 Forbidden
- User Action: Upload a pre-existing invoice instead

**Customer Download of PENDING Invoice:**
- Error Message: "Invoice not available for pending shipments"
- HTTP Status: 403 Forbidden
- User Action: Wait for shipment to be booked

### Error Handling Strategy

1. **Validation Errors**: Caught at form level before processing; display inline field errors
2. **Permission Errors**: Checked in views; return 403 with clear message
3. **File System Errors**: Wrapped in try-except blocks; log details and show generic user message
4. **PDF Generation Errors**: Wrapped in try-except blocks; log full traceback for debugging
5. **Database Errors**: Django's built-in transaction handling; rollback on failure

## Testing Strategy

### Overview

The Commercial Invoice System will be tested using a dual approach combining unit tests for specific scenarios and property-based tests for universal behaviors. This ensures both concrete edge cases and general correctness across a wide range of inputs.

### Testing Framework

- **Unit Testing**: Django's built-in `TestCase` framework
- **Property-Based Testing**: Hypothesis library for Python
- **Test Configuration**: Minimum 100 iterations per property test
- **Coverage Target**: 90%+ code coverage for invoice-related code

### Unit Tests

Unit tests will focus on specific examples, edge cases, and integration points:

**File Upload Tests:**
- Upload valid PDF file
- Upload valid image file (JPG, PNG)
- Upload invalid file format (e.g., .txt, .docx)
- Upload file exceeding 10MB
- Upload when invoice already exists
- Upload during shipment creation
- Upload after shipment creation

**Invoice Generation Tests:**
- Generate invoice with single line item
- Generate invoice with multiple line items
- Generate invoice without AWB (should fail)
- Generate invoice when invoice already exists (should fail)
- Generate invoice with zero line items (should fail)
- Generate invoice as customer (should fail)

**Invoice Deletion Tests:**
- Staff deletes invoice from PENDING shipment
- Staff deletes invoice from BOOKED shipment
- Customer deletes invoice from PENDING shipment
- Customer attempts to delete invoice from BOOKED shipment (should fail)
- Delete non-existent invoice (should fail)

**UI Rendering Tests:**
- Render shipment detail for staff with no invoice
- Render shipment detail for staff with invoice
- Render shipment detail for customer with PENDING shipment and no invoice
- Render shipment detail for customer with PENDING shipment and invoice
- Render shipment detail for customer with BOOKED shipment and invoice
- Verify correct buttons are visible in each scenario

**PDF Content Tests:**
- Verify PDF contains all required fields
- Verify PDF total calculation is correct
- Verify PDF uses correct currency
- Verify PDF contains edited shipper/consignee values (not database values)

### Property-Based Tests

Property-based tests will verify universal behaviors across randomly generated inputs. Each test will run a minimum of 100 iterations.

**Property Test 1: Upload File Validation**
```python
@given(
    file_extension=st.sampled_from(['pdf', 'jpg', 'jpeg', 'png', 'txt', 'docx', 'exe']),
    file_size=st.integers(min_value=1, max_value=20*1024*1024)
)
@settings(max_examples=100)
def test_upload_validation(file_extension, file_size):
    """
    Feature: commercial-invoice-system, Property 1: 
    For any file upload attempt, the system should accept the file 
    if and only if it is a PDF or image format and does not exceed 10MB.
    """
    # Test implementation
```

**Property Test 2: Invoice Storage After Upload**
```python
@given(
    shipment=shipment_strategy(),
    file_content=st.binary(min_size=100, max_size=5*1024*1024)
)
@settings(max_examples=100)
def test_invoice_storage(shipment, file_content):
    """
    Feature: commercial-invoice-system, Property 2:
    For any valid file upload to a shipment without an existing invoice,
    the shipment's invoice field should contain the uploaded file.
    """
    # Test implementation
```

**Property Test 3: Single Invoice Constraint**
```python
@given(shipment_with_invoice=shipment_with_invoice_strategy())
@settings(max_examples=100)
def test_single_invoice_constraint(shipment_with_invoice):
    """
    Feature: commercial-invoice-system, Property 3:
    For any shipment with an existing invoice, attempts to upload or 
    generate a new invoice should fail.
    """
    # Test implementation
```

**Property Test 4: Customer Download Access by Status**
```python
@given(
    shipment=shipment_strategy(),
    status=st.sampled_from(['PENDING', 'BOOKED', 'IN_TRANSIT_TO_HK', 'DELIVERED_IN_HK'])
)
@settings(max_examples=100)
def test_customer_download_access(shipment, status):
    """
    Feature: commercial-invoice-system, Property 4:
    For any shipment with an invoice where the user is a customer,
    download buttons should be visible if and only if status is BOOKED or later.
    """
    # Test implementation
```

**Property Test 5: Invoice File Download**
```python
@given(shipment_with_invoice=shipment_with_invoice_strategy())
@settings(max_examples=100)
def test_invoice_download(shipment_with_invoice):
    """
    Feature: commercial-invoice-system, Property 5:
    For any shipment with an invoice, download should serve the exact file.
    """
    # Test implementation
```

**Property Test 6: Staff Delete Access**
```python
@given(
    shipment_with_invoice=shipment_with_invoice_strategy(),
    status=st.sampled_from(Shipment.STATUS_CHOICES)
)
@settings(max_examples=100)
def test_staff_delete_access(shipment_with_invoice, status):
    """
    Feature: commercial-invoice-system, Property 6:
    For any shipment with an invoice where user is staff,
    delete button should be visible regardless of status.
    """
    # Test implementation
```

**Property Test 7: Customer Delete Access by Status**
```python
@given(
    shipment_with_invoice=shipment_with_invoice_strategy(),
    status=st.sampled_from(['PENDING', 'BOOKED', 'IN_TRANSIT_TO_HK'])
)
@settings(max_examples=100)
def test_customer_delete_access(shipment_with_invoice, status):
    """
    Feature: commercial-invoice-system, Property 7:
    For any shipment with an invoice where user is customer,
    delete button should be visible if and only if status is PENDING.
    """
    # Test implementation
```

**Property Test 8: Invoice Deletion Cleanup**
```python
@given(shipment_with_invoice=shipment_with_invoice_strategy())
@settings(max_examples=100)
def test_deletion_cleanup(shipment_with_invoice):
    """
    Feature: commercial-invoice-system, Property 8:
    For any shipment with an invoice, after deletion, file should be 
    removed from storage and invoice field should be null.
    """
    # Test implementation
```

**Property Test 9: Form Pre-population**
```python
@given(shipment=shipment_with_awb_strategy())
@settings(max_examples=100)
def test_form_prepopulation(shipment):
    """
    Feature: commercial-invoice-system, Property 9:
    For any shipment, invoice generation form should be pre-populated
    with shipper, consignee, and AWB data from the shipment.
    """
    # Test implementation
```

**Property Test 10: Shipper/Consignee Override Isolation**
```python
@given(
    shipment=shipment_with_awb_strategy(),
    override_shipper=st.text(min_size=1, max_size=200),
    override_consignee=st.text(min_size=1, max_size=200)
)
@settings(max_examples=100)
def test_override_isolation(shipment, override_shipper, override_consignee):
    """
    Feature: commercial-invoice-system, Property 10:
    For any invoice generation with edited shipper/consignee fields,
    PDF should contain edited values but database should remain unchanged.
    """
    # Test implementation
```

**Property Test 11: Multiple Line Items Support**
```python
@given(
    shipment=shipment_with_awb_strategy(),
    line_items=st.lists(line_item_strategy(), min_size=1, max_size=20)
)
@settings(max_examples=100)
def test_multiple_line_items(shipment, line_items):
    """
    Feature: commercial-invoice-system, Property 11:
    For any invoice generation with N line items, all N should be 
    captured and included in the PDF.
    """
    # Test implementation
```

**Property Test 12: PDF Generation and Storage**
```python
@given(
    shipment=shipment_with_awb_strategy(),
    line_items=st.lists(line_item_strategy(), min_size=1, max_size=10)
)
@settings(max_examples=100)
def test_pdf_generation_storage(shipment, line_items):
    """
    Feature: commercial-invoice-system, Property 12:
    For any valid invoice generation, system should generate PDF
    and store it in shipment's invoice field.
    """
    # Test implementation
```

**Property Test 13: Line Item Non-Persistence**
```python
@given(
    shipment=shipment_with_awb_strategy(),
    line_items=st.lists(line_item_strategy(), min_size=1, max_size=10)
)
@settings(max_examples=100)
def test_line_item_non_persistence(shipment, line_items):
    """
    Feature: commercial-invoice-system, Property 13:
    For any invoice generation, no line item records should exist
    in the database after PDF creation.
    """
    # Test implementation
```

**Property Test 14: PDF Content Completeness**
```python
@given(
    shipment=shipment_with_awb_strategy(),
    line_items=st.lists(line_item_strategy(), min_size=1, max_size=10)
)
@settings(max_examples=100)
def test_pdf_content_completeness(shipment, line_items):
    """
    Feature: commercial-invoice-system, Property 14:
    For any generated PDF, document should contain shipper, consignee,
    AWB, line item table, and currency.
    """
    # Test implementation
```

**Property Test 15: PDF Total Calculation**
```python
@given(line_items=st.lists(line_item_strategy(), min_size=1, max_size=10))
@settings(max_examples=100)
def test_pdf_total_calculation(line_items):
    """
    Feature: commercial-invoice-system, Property 15:
    For any generated PDF, total value should equal sum of 
    (quantity × unit_value) for all line items.
    """
    # Test implementation
```

**Property Test 16: AWB Prerequisite Enforcement**
```python
@given(shipment_without_awb=shipment_without_awb_strategy())
@settings(max_examples=100)
def test_awb_prerequisite(shipment_without_awb):
    """
    Feature: commercial-invoice-system, Property 16:
    For any shipment without AWB, invoice generation should fail.
    """
    # Test implementation
```

**Property Test 17: Line Item Field Validation**
```python
@given(
    line_item=st.builds(
        dict,
        description=st.one_of(st.just(''), st.text()),
        weight=st.one_of(st.just(''), st.decimals()),
        quantity=st.one_of(st.just(''), st.integers()),
        unit_value=st.one_of(st.just(''), st.decimals())
    )
)
@settings(max_examples=100)
def test_line_item_field_validation(line_item):
    """
    Feature: commercial-invoice-system, Property 17:
    For any line item, system should reject if any required field is empty.
    """
    # Test implementation
```

**Property Test 18: Positive Numeric Validation**
```python
@given(
    weight=st.decimals(allow_nan=False, allow_infinity=False),
    quantity=st.integers(),
    unit_value=st.decimals(allow_nan=False, allow_infinity=False)
)
@settings(max_examples=100)
def test_positive_numeric_validation(weight, quantity, unit_value):
    """
    Feature: commercial-invoice-system, Property 18:
    For any line item, system should reject if weight/quantity/unit_value
    are not positive.
    """
    # Test implementation
```

**Property Test 19: Validation Error Messaging**
```python
@given(invalid_line_item=invalid_line_item_strategy())
@settings(max_examples=100)
def test_validation_error_messaging(invalid_line_item):
    """
    Feature: commercial-invoice-system, Property 19:
    For any validation failure, system should display specific error messages.
    """
    # Test implementation
```

### Test Data Strategies

Hypothesis strategies for generating test data:

```python
from hypothesis import strategies as st

@st.composite
def shipment_strategy(draw):
    """Generate a random shipment."""
    return Shipment.objects.create(
        direction='BD_TO_HK',
        shipper_name=draw(st.text(min_size=1, max_size=200)),
        shipper_address=draw(st.text(min_size=1, max_size=500)),
        recipient_name=draw(st.text(min_size=1, max_size=200)),
        recipient_address=draw(st.text(min_size=1, max_size=500)),
        declared_value=draw(st.decimals(min_value=1, max_value=10000, places=2)),
        declared_currency=draw(st.sampled_from(['USD', 'HKD', 'BDT'])),
        weight_estimated=draw(st.decimals(min_value=0.1, max_value=100, places=2)),
        current_status=draw(st.sampled_from(['PENDING', 'BOOKED'])),
        # ... other required fields
    )

@st.composite
def shipment_with_awb_strategy(draw):
    """Generate a shipment with AWB number."""
    shipment = draw(shipment_strategy())
    shipment.current_status = 'BOOKED'
    shipment.save()  # Triggers AWB generation
    return shipment

@st.composite
def shipment_without_awb_strategy(draw):
    """Generate a shipment without AWB number."""
    shipment = draw(shipment_strategy())
    shipment.current_status = 'PENDING'
    shipment.awb_number = None
    shipment.save()
    return shipment

@st.composite
def line_item_strategy(draw):
    """Generate a valid line item."""
    return {
        'description': draw(st.text(min_size=1, max_size=500)),
        'weight': draw(st.decimals(min_value=0.01, max_value=100, places=2)),
        'quantity': draw(st.integers(min_value=1, max_value=1000)),
        'unit_value': draw(st.decimals(min_value=0.01, max_value=10000, places=2))
    }

@st.composite
def invalid_line_item_strategy(draw):
    """Generate an invalid line item for testing validation."""
    return draw(st.one_of(
        st.builds(dict, description=st.just(''), weight=st.decimals(), 
                  quantity=st.integers(), unit_value=st.decimals()),
        st.builds(dict, description=st.text(), weight=st.decimals(max_value=0), 
                  quantity=st.integers(), unit_value=st.decimals()),
        st.builds(dict, description=st.text(), weight=st.decimals(), 
                  quantity=st.integers(max_value=0), unit_value=st.decimals()),
        st.builds(dict, description=st.text(), weight=st.decimals(), 
                  quantity=st.integers(), unit_value=st.decimals(max_value=0))
    ))
```

### Integration Tests

Integration tests will verify end-to-end workflows:

1. **Complete Upload Workflow**: Create shipment → Upload invoice → View invoice → Delete invoice
2. **Complete Generation Workflow**: Create shipment → Book shipment → Generate invoice → Download invoice
3. **Permission Workflow**: Test all permission scenarios across different user roles and shipment statuses
4. **Error Recovery**: Test system behavior after various error conditions

### Test Execution

```bash
# Run all tests
python manage.py test exportimport.tests.test_invoice

# Run only unit tests
python manage.py test exportimport.tests.test_invoice.InvoiceUnitTests

# Run only property tests
python manage.py test exportimport.tests.test_invoice.InvoicePropertyTests

# Run with coverage
coverage run --source='exportimport' manage.py test exportimport.tests.test_invoice
coverage report
```

### Continuous Integration

- All tests must pass before merging to main branch
- Property tests run with 100 iterations in CI
- Coverage reports generated and tracked over time
- Failed property tests should include the failing example for reproduction


## UI Components

### Shipment Detail Page Template

The shipment detail page will be modified to include invoice management functionality. All permission checks will be implemented using Django template conditionals.

**Template: `templates/exportimport/shipment_detail.html`**

```django
{% extends "base.html" %}

{% block content %}
<div class="shipment-detail">
    <h1>Shipment Details: {{ shipment.awb_number|default:"PENDING" }}</h1>
    
    <!-- Existing shipment information -->
    <div class="shipment-info">
        <!-- ... existing fields ... -->
    </div>
    
    <!-- Invoice Section -->
    <div class="invoice-section">
        <h2>Commercial Invoice</h2>
        
        {% if shipment.invoice %}
            <!-- Invoice exists: show download, preview, and delete buttons -->
            <div class="invoice-actions">
                <p>Invoice attached: {{ shipment.invoice.name }}</p>
                
                <!-- Download button: Staff always, Customer only if BOOKED or later -->
                {% if request.user.is_staff or shipment.current_status != 'PENDING' %}
                    <a href="{% url 'invoice_download' shipment.id %}" class="btn btn-primary">
                        Download Invoice
                    </a>
                    <a href="{% url 'invoice_download' shipment.id %}?preview=1" 
                       class="btn btn-secondary" target="_blank">
                        Preview Invoice
                    </a>
                {% endif %}
                
                <!-- Delete button: Staff always, Customer only if PENDING -->
                {% if request.user.is_staff or shipment.current_status == 'PENDING' %}
                    <a href="{% url 'invoice_delete' shipment.id %}" class="btn btn-danger">
                        Delete Invoice
                    </a>
                {% endif %}
            </div>
        {% else %}
            <!-- No invoice: show upload and generation options -->
            <div class="invoice-create">
                <p>No invoice attached</p>
                
                <!-- Upload option: Always visible when no invoice -->
                <div class="upload-section">
                    <h3>Upload Invoice</h3>
                    <a href="{% url 'invoice_upload' shipment.id %}" class="btn btn-primary">
                        Upload Invoice File
                    </a>
                </div>
                
                <!-- Generate option: Staff only, requires AWB -->
                {% if request.user.is_staff and shipment.awb_number %}
                    <div class="generate-section">
                        <h3>Generate Invoice</h3>
                        <a href="{% url 'invoice_generate' shipment.id %}" class="btn btn-success">
                            Create Invoice
                        </a>
                    </div>
                {% endif %}
            </div>
        {% endif %}
    </div>
</div>
{% endblock %}
```

### Invoice Upload Template

**Template: `templates/exportimport/invoice_upload.html`**

```django
{% extends "base.html" %}

{% block content %}
<div class="invoice-upload">
    <h1>Upload Invoice</h1>
    <h2>Shipment: {{ shipment.awb_number|default:"PENDING" }}</h2>
    
    <form method="post" enctype="multipart/form-data">
        {% csrf_token %}
        
        <div class="form-group">
            <label for="{{ form.invoice.id_for_label }}">Invoice File:</label>
            {{ form.invoice }}
            {% if form.invoice.errors %}
                <div class="error">{{ form.invoice.errors }}</div>
            {% endif %}
            <small class="form-text">
                Accepted formats: PDF, JPG, JPEG, PNG. Maximum size: 10MB.
            </small>
        </div>
        
        <div class="form-actions">
            <button type="submit" class="btn btn-primary">Upload</button>
            <a href="{% url 'shipment_detail' shipment.id %}" class="btn btn-secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}
```

### Invoice Generation Template

**Template: `templates/exportimport/invoice_generate.html`**

```django
{% extends "base.html" %}

{% block content %}
<div class="invoice-generate">
    <h1>Generate Invoice</h1>
    <h2>Shipment: {{ shipment.awb_number }}</h2>
    
    <form method="post" id="invoice-form">
        {% csrf_token %}
        
        <!-- Shipper Information -->
        <fieldset>
            <legend>Shipper Information</legend>
            
            <div class="form-group">
                <label for="{{ form.shipper_name.id_for_label }}">Shipper Name:</label>
                {{ form.shipper_name }}
                {% if form.shipper_name.errors %}
                    <div class="error">{{ form.shipper_name.errors }}</div>
                {% endif %}
            </div>
            
            <div class="form-group">
                <label for="{{ form.shipper_address.id_for_label }}">Shipper Address:</label>
                {{ form.shipper_address }}
                {% if form.shipper_address.errors %}
                    <div class="error">{{ form.shipper_address.errors }}</div>
                {% endif %}
            </div>
        </fieldset>
        
        <!-- Consignee Information -->
        <fieldset>
            <legend>Consignee Information</legend>
            
            <div class="form-group">
                <label for="{{ form.consignee_name.id_for_label }}">Consignee Name:</label>
                {{ form.consignee_name }}
                {% if form.consignee_name.errors %}
                    <div class="error">{{ form.consignee_name.errors }}</div>
                {% endif %}
            </div>
            
            <div class="form-group">
                <label for="{{ form.consignee_address.id_for_label }}">Consignee Address:</label>
                {{ form.consignee_address }}
                {% if form.consignee_address.errors %}
                    <div class="error">{{ form.consignee_address.errors }}</div>
                {% endif %}
            </div>
        </fieldset>
        
        <!-- AWB Number (Read-only) -->
        <fieldset>
            <legend>Shipment Information</legend>
            
            <div class="form-group">
                <label for="{{ form.awb_number.id_for_label }}">AWB Number:</label>
                {{ form.awb_number }}
                <small class="form-text">This field cannot be edited.</small>
            </div>
        </fieldset>
        
        <!-- Product Line Items -->
        <fieldset id="line-items-section">
            <legend>Product Line Items</legend>
            
            {{ formset.management_form }}
            
            <div id="line-items-container">
                {% for form in formset %}
                    <div class="line-item" data-form-index="{{ forloop.counter0 }}">
                        <h4>Item {{ forloop.counter }}</h4>
                        
                        <div class="form-group">
                            <label>Description:</label>
                            {{ form.description }}
                            {% if form.description.errors %}
                                <div class="error">{{ form.description.errors }}</div>
                            {% endif %}
                        </div>
                        
                        <div class="form-row">
                            <div class="form-group">
                                <label>Weight (kg):</label>
                                {{ form.weight }}
                                {% if form.weight.errors %}
                                    <div class="error">{{ form.weight.errors }}</div>
                                {% endif %}
                            </div>
                            
                            <div class="form-group">
                                <label>Quantity:</label>
                                {{ form.quantity }}
                                {% if form.quantity.errors %}
                                    <div class="error">{{ form.quantity.errors }}</div>
                                {% endif %}
                            </div>
                            
                            <div class="form-group">
                                <label>Unit Value ({{ shipment.declared_currency }}):</label>
                                {{ form.unit_value }}
                                {% if form.unit_value.errors %}
                                    <div class="error">{{ form.unit_value.errors }}</div>
                                {% endif %}
                            </div>
                        </div>
                        
                        {% if not forloop.first %}
                            <button type="button" class="btn btn-danger btn-sm remove-item">
                                Remove Item
                            </button>
                        {% endif %}
                    </div>
                {% endfor %}
            </div>
            
            <button type="button" id="add-item" class="btn btn-secondary">
                Add Another Item
            </button>
        </fieldset>
        
        <div class="form-actions">
            <button type="submit" class="btn btn-primary">Generate Invoice</button>
            <a href="{% url 'shipment_detail' shipment.id %}" class="btn btn-secondary">Cancel</a>
        </div>
    </form>
</div>

<script>
// JavaScript for dynamic formset management
document.addEventListener('DOMContentLoaded', function() {
    const container = document.getElementById('line-items-container');
    const addButton = document.getElementById('add-item');
    const totalForms = document.querySelector('[name$="-TOTAL_FORMS"]');
    
    let formCount = parseInt(totalForms.value);
    
    addButton.addEventListener('click', function() {
        const newForm = container.querySelector('.line-item').cloneNode(true);
        
        // Update form index
        newForm.setAttribute('data-form-index', formCount);
        newForm.querySelector('h4').textContent = 'Item ' + (formCount + 1);
        
        // Update field names and IDs
        newForm.querySelectorAll('input, textarea').forEach(function(field) {
            const name = field.getAttribute('name').replace(/-\d+-/, '-' + formCount + '-');
            const id = field.getAttribute('id').replace(/_\d+_/, '_' + formCount + '_');
            field.setAttribute('name', name);
            field.setAttribute('id', id);
            field.value = '';
        });
        
        // Clear errors
        newForm.querySelectorAll('.error').forEach(el => el.remove());
        
        // Add remove button if not present
        if (!newForm.querySelector('.remove-item')) {
            const removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'btn btn-danger btn-sm remove-item';
            removeBtn.textContent = 'Remove Item';
            newForm.appendChild(removeBtn);
        }
        
        container.appendChild(newForm);
        formCount++;
        totalForms.value = formCount;
    });
    
    container.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-item')) {
            e.target.closest('.line-item').remove();
            formCount--;
            totalForms.value = formCount;
            
            // Renumber remaining items
            container.querySelectorAll('.line-item').forEach(function(item, index) {
                item.querySelector('h4').textContent = 'Item ' + (index + 1);
            });
        }
    });
});
</script>
{% endblock %}
```

### Invoice Delete Confirmation Template

**Template: `templates/exportimport/invoice_delete_confirm.html`**

```django
{% extends "base.html" %}

{% block content %}
<div class="invoice-delete">
    <h1>Delete Invoice</h1>
    <h2>Shipment: {{ shipment.awb_number|default:"PENDING" }}</h2>
    
    <div class="warning">
        <p>Are you sure you want to delete this invoice?</p>
        <p><strong>This action cannot be undone.</strong></p>
        <p>Invoice: {{ shipment.invoice.name }}</p>
    </div>
    
    <form method="post">
        {% csrf_token %}
        <div class="form-actions">
            <button type="submit" class="btn btn-danger">Yes, Delete Invoice</button>
            <a href="{% url 'shipment_detail' shipment.id %}" class="btn btn-secondary">Cancel</a>
        </div>
    </form>
</div>
{% endblock %}
```

## URL Configuration

### URL Patterns

Add the following URL patterns to `exportimport/urls.py`:

```python
from django.urls import path
from . import views

urlpatterns = [
    # ... existing patterns ...
    
    # Invoice management URLs
    path('shipment/<int:shipment_id>/invoice/upload/', 
         views.invoice_upload_view, 
         name='invoice_upload'),
    
    path('shipment/<int:shipment_id>/invoice/generate/', 
         views.invoice_generate_view, 
         name='invoice_generate'),
    
    path('shipment/<int:shipment_id>/invoice/delete/', 
         views.invoice_delete_view, 
         name='invoice_delete'),
    
    path('shipment/<int:shipment_id>/invoice/download/', 
         views.invoice_download_view, 
         name='invoice_download'),
]
```

## Implementation Notes

### Dependencies

Add the following to `requirements.txt`:

```
reportlab>=3.6.0  # For PDF generation
Pillow>=9.0.0     # For image handling
hypothesis>=6.0.0  # For property-based testing
```

### Settings Configuration

Add to `config/settings.py`:

```python
# Media files configuration
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# File upload settings
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB in bytes
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB in bytes
```

### URL Configuration for Media Files

Add to `config/urls.py` (for development):

```python
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ... existing patterns ...
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

### Migration Steps

1. Create migration: `python manage.py makemigrations`
2. Review migration file
3. Apply migration: `python manage.py migrate`
4. Create media directory: `mkdir -p media/invoices`
5. Set appropriate permissions on media directory

### Security Considerations

1. **File Validation**: Always validate file type and size on the server side
2. **Access Control**: Verify user permissions in views before serving files
3. **File Storage**: Store uploaded files outside the web root
4. **Filename Sanitization**: Use Django's file storage to handle filename sanitization
5. **CSRF Protection**: Ensure all forms include CSRF tokens
6. **SQL Injection**: Use Django ORM to prevent SQL injection
7. **XSS Prevention**: Django templates auto-escape by default

### Performance Considerations

1. **File Storage**: Consider using cloud storage (S3, GCS) for production
2. **PDF Generation**: Generate PDFs asynchronously for large invoices (future enhancement)
3. **Caching**: Cache shipment detail pages with appropriate invalidation
4. **Database Indexing**: Ensure `awb_number` and `invoice` fields are indexed
5. **File Serving**: Use web server (nginx) to serve media files in production

## Future Enhancements

While not part of the current requirements, these enhancements could be considered:

1. **Multiple Invoices**: Support multiple invoices per shipment with versioning
2. **Invoice Templates**: Customizable PDF templates for different customers
3. **Automatic Generation**: Auto-generate invoices from shipment data
4. **Email Delivery**: Email invoices to customers automatically
5. **Invoice History**: Track all invoice changes and deletions
6. **Bulk Operations**: Upload/generate invoices for multiple shipments
7. **OCR Integration**: Extract data from uploaded invoice images
8. **Digital Signatures**: Support for digitally signed invoices
9. **Multi-currency**: Automatic currency conversion in invoices
10. **Audit Trail**: Comprehensive logging of all invoice operations

## Conclusion

This design provides a simple, maintainable solution for commercial invoice management that integrates seamlessly with the existing Django shipment application. The single-field approach minimizes database complexity while the template-based permission system ensures clear, maintainable access control. The dual testing strategy with both unit and property-based tests ensures comprehensive coverage and correctness across all scenarios.
