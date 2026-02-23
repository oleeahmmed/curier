# Requirements Document

## Introduction

This document specifies requirements for a simplified Commercial Invoice System to be integrated into an existing Django-based export/import shipment management application. The system enables staff and customers to manage a single invoice file per shipment, either by uploading an existing invoice document or by generating one with product line items. Only one invoice can exist per shipment at a time. To replace an invoice, the existing invoice must be deleted first, after which staff can upload or generate a new one. All invoices must contain product line items with commercial values.

## Glossary

- **System**: The Commercial Invoice System
- **Shipment**: A booking record in the Django application containing AWB number, customer, parcels, and bags
- **AWB**: Air Waybill number, a unique identifier assigned when a shipment is booked
- **Invoice**: A single PDF or image file field on the Shipment model
- **Staff**: Authenticated users with administrative privileges to create, delete, and manage invoices without restrictions
- **Customer**: Authenticated users who create shipments and may upload invoice documents with restrictions based on shipment status
- **Shipment_Status**: The current state of a shipment (e.g., PENDING, BOOKED, IN_TRANSIT, DELIVERED)
- **PENDING**: Shipment status indicating the shipment has not yet been booked
- **BOOKED**: Shipment status indicating the shipment has been confirmed and assigned an AWB number
- **Product_Line_Item**: Temporary data used during PDF generation containing description, weight, quantity, and value
- **Shipper**: The party sending the shipment
- **Consignee**: The party receiving the shipment

## Requirements

### Requirement 1: Invoice Upload Capability

**User Story:** As a customer or staff member, I want to upload an invoice document, so that I can attach pre-prepared invoices to shipments.

#### Acceptance Criteria

1. THE System SHALL accept PDF and image file formats for invoice uploads
2. WHEN a user uploads an invoice file, THE System SHALL store the file in the shipment's invoice field
3. THE System SHALL allow invoice uploads during shipment creation or after shipment creation
4. THE System SHALL validate uploaded file size does not exceed 10MB
5. WHEN the user is a customer, THE System SHALL display only the upload option for invoice management
6. WHEN the user is staff AND no invoice exists, THE System SHALL display both the upload option and the "Create Invoice" button for invoice management
7. WHEN an invoice already exists, THE System SHALL hide the upload option and "Create Invoice" button
8. WHEN an invoice already exists, THE System SHALL require deletion of the existing invoice before allowing upload or generation of a new invoice

### Requirement 2: Invoice Viewing and Download

**User Story:** As a staff member or customer, I want to view and download the invoice associated with a shipment, so that I can access invoice documentation when needed.

#### Acceptance Criteria

1. WHEN a shipment has an invoice AND the user is staff, THE System SHALL display download and preview buttons on the shipment detail page
2. WHEN a shipment has an invoice AND the user is a customer AND the shipment status is BOOKED or later, THE System SHALL display download and preview buttons on the shipment detail page
3. WHEN a shipment has an invoice AND the user is a customer AND the shipment status is PENDING, THE System SHALL hide download and preview buttons
4. WHEN a user clicks the download button, THE System SHALL serve the invoice file
5. WHEN a shipment has no invoice, THE System SHALL display an indicator that no invoice exists

### Requirement 3: Invoice Deletion

**User Story:** As a staff member or customer, I want to delete an invoice, so that I can remove incorrect invoices or prepare to upload a replacement.

#### Acceptance Criteria

1. WHEN the user is staff, THE System SHALL display a delete button for invoices regardless of shipment status
2. WHEN the user is a customer AND the shipment status is PENDING, THE System SHALL display a delete button for invoices
3. WHEN the user is a customer AND the shipment status is BOOKED or later, THE System SHALL hide the delete button for invoices
4. WHEN a user deletes an invoice, THE System SHALL remove the file from storage
5. WHEN a user deletes an invoice, THE System SHALL clear the invoice field on the shipment
6. WHEN an invoice is deleted, THE System SHALL enable invoice upload and generation options

### Requirement 4: Manual Invoice Generation

**User Story:** As a staff member, I want to generate an invoice with product line items, so that I can create invoices for shipments without pre-existing documentation.

#### Acceptance Criteria

1. WHEN a shipment has an AWB number AND no invoice exists AND the user is staff, THE System SHALL display the "Create Invoice" button
2. WHEN an invoice already exists, THE System SHALL hide the "Create Invoice" button
3. WHEN the user is a customer, THE System SHALL hide the manual invoice generation interface
4. THE System SHALL pre-populate the shipper name field with data from the shipment record
5. THE System SHALL pre-populate the shipper address field with data from the shipment record
6. THE System SHALL pre-populate the consignee name field with data from the shipment record
7. THE System SHALL pre-populate the consignee address field with data from the shipment record
8. THE System SHALL allow staff to edit the shipper name field in the invoice generation form
9. THE System SHALL allow staff to edit the shipper address field in the invoice generation form
10. THE System SHALL allow staff to edit the consignee name field in the invoice generation form
11. THE System SHALL allow staff to edit the consignee address field in the invoice generation form
12. WHEN staff edits shipper or consignee fields, THE System SHALL use the edited values only for PDF generation
13. WHEN staff edits shipper or consignee fields, THE System SHALL not update the shipment database with the edited values
14. THE System SHALL display the AWB number field as read-only in the invoice generation form
15. THE System SHALL populate the AWB number field from the shipment record
16. THE System SHALL prevent staff from editing the AWB number field
17. THE System SHALL allow staff to add multiple product line items to the invoice
18. FOR EACH product line item, THE System SHALL capture description, weight, quantity, and unit value
19. WHEN staff saves the invoice, THE System SHALL generate a PDF document
20. WHEN the PDF is generated, THE System SHALL store the PDF in the invoice field
21. THE System SHALL use product line items only for PDF generation and not persist them after generation

### Requirement 5: Invoice PDF Generation

**User Story:** As a staff member, I want the system to generate professional PDF invoices, so that I can provide standardized documentation to customers and customs authorities.

#### Acceptance Criteria

1. WHEN an invoice is generated, THE System SHALL create a PDF document
2. THE PDF SHALL display shipper name and address
3. THE PDF SHALL display consignee name and address
4. THE PDF SHALL display a table with columns for description, weight, quantity, and value
5. THE PDF SHALL display the total value calculated from all line items
6. THE PDF SHALL display the AWB number
7. THE PDF SHALL use the currency specified in the shipment's declared_currency field

### Requirement 6: AWB Prerequisite Enforcement

**User Story:** As a system administrator, I want invoice generation to be restricted to booked shipments, so that invoices are only generated for confirmed shipments with AWB numbers.

#### Acceptance Criteria

1. WHEN a shipment does not have an AWB number, THE System SHALL hide the manual invoice generation interface
2. WHEN a shipment does not have an AWB number, THE System SHALL prevent invoice generation via API calls
3. WHEN a shipment has an AWB number AND no invoice exists, THE System SHALL display the "Create Invoice" button on the shipment detail page

### Requirement 7: Basic Invoice Data Validation

**User Story:** As a staff member, I want the system to validate invoice data, so that I can ensure invoice accuracy before generation.

#### Acceptance Criteria

1. WHEN generating an invoice, THE System SHALL require at least one product line item
2. FOR EACH product line item, THE System SHALL require description, weight, quantity, and unit value fields to be non-empty
3. THE System SHALL validate that weight values are positive numbers
4. THE System SHALL validate that quantity values are positive integers
5. THE System SHALL validate that unit value amounts are positive numbers
6. WHEN validation fails, THE System SHALL display error messages indicating which fields are invalid

### Requirement 8: Template-Based Permission Enforcement

**User Story:** As a developer, I want permissions to be enforced in templates using conditional logic, so that the UI correctly reflects user capabilities based on role, shipment status, and invoice existence.

#### Acceptance Criteria

1. THE System SHALL use Django template conditional statements to control visibility of invoice action buttons
2. THE System SHALL evaluate user role (staff or customer) in template logic
3. THE System SHALL evaluate shipment status in template logic
4. THE System SHALL evaluate invoice existence in template logic
5. WHEN rendering the delete button, THE System SHALL check if user is staff OR (user is customer AND shipment status is PENDING)
6. WHEN rendering download and preview buttons, THE System SHALL check if user is staff OR (user is customer AND shipment status is BOOKED or later)
7. WHEN rendering the "Create Invoice" button, THE System SHALL check if user is staff AND no invoice exists
8. WHEN rendering the invoice upload interface, THE System SHALL check if no invoice exists
9. WHEN an invoice exists, THE System SHALL display download, preview, and delete buttons only
10. WHEN no invoice exists, THE System SHALL display upload option and "Create Invoice" button (for staff only)
11. WHEN the user is a customer, THE System SHALL display only the upload option when no invoice exists
12. THE System SHALL not implement view-level permission checks for these invoice actions
