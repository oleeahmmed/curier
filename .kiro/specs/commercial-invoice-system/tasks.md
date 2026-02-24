# Implementation Plan: Commercial Invoice System

## Overview

This plan implements a commercial invoice management system for a Django-based shipment application. The system supports uploading existing invoice files (PDF/images) or generating invoices with product line items. Key features include single invoice per shipment constraint, template-based permission enforcement, and temporary line item handling during PDF generation.

## Tasks

- [x] 1. Set up project dependencies and configuration
  - Install required packages: reportlab, Pillow, hypothesis
  - Configure media file settings (MEDIA_URL, MEDIA_ROOT, file upload limits)
  - Add media URL patterns for development
  - Create media/invoices directory structure
  - _Requirements: 1.1, 1.4_

- [x] 2. Create database migration for invoice field
  - [x] 2.1 Add invoice FileField to Shipment model
    - Add field with upload_to='invoices/%Y/%m/', blank=True, null=True
    - Include help text for field documentation
    - _Requirements: 1.2_
  
  - [x] 2.2 Generate and apply migration
    - Run makemigrations command
    - Review generated migration file
    - Apply migration to database
    - _Requirements: 1.2_

- [x] 3. Implement invoice forms
  - [x] 3.1 Create InvoiceUploadForm
    - Implement ModelForm for Shipment.invoice field
    - Add clean_invoice method with file extension validation (PDF, JPG, JPEG, PNG)
    - Add file size validation (10MB maximum)
    - _Requirements: 1.1, 1.4_
  
  - [ ]* 3.2 Write property test for upload form validation
    - **Property 1: Upload File Validation**
    - **Validates: Requirements 1.1, 1.4**
  
  - [x] 3.3 Create InvoiceGenerationForm
    - Add shipper_name and shipper_address fields (editable)
    - Add consignee_name and consignee_address fields (editable)
    - Add awb_number field (disabled, read-only)
    - Implement __init__ to pre-populate from shipment
    - _Requirements: 4.4, 4.5, 4.6, 4.7, 4.14, 4.15, 4.16_
  
  - [ ]* 3.4 Write property test for form pre-population
    - **Property 9: Form Pre-population from Shipment**
    - **Validates: Requirements 4.4, 4.5, 4.6, 4.7, 4.15**
  
  - [x] 3.5 Create ProductLineItemForm and formset
    - Add description, weight, quantity, unit_value fields
    - Set appropriate field types and validation (DecimalField, IntegerField)
    - Add min_value constraints for numeric fields
    - Create formset_factory with min_num=1
    - _Requirements: 4.17, 4.18, 7.2, 7.3, 7.4, 7.5_
  
  - [ ]* 3.6 Write property tests for line item validation
    - **Property 17: Line Item Field Validation**
    - **Property 18: Positive Numeric Validation**
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.5**

- [ ] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement PDF generation service
  - [x] 5.1 Create generate_invoice_pdf function
    - Set up ReportLab document with letter page size
    - Add title section with "COMMERCIAL INVOICE" heading
    - Add AWB number display
    - Create shipper/consignee information table
    - Build product line items table with description, weight, quantity, unit value, total columns
    - Calculate and display total value
    - Return BytesIO buffer containing PDF
    - _Requirements: 4.19, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  
  - [ ]* 5.2 Write unit tests for PDF generation
    - Test PDF generation with single line item
    - Test PDF generation with multiple line items
    - Test total calculation accuracy
    - Test currency display from shipment.declared_currency
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_
  
  - [ ]* 5.3 Write property tests for PDF content
    - **Property 14: PDF Content Completeness**
    - **Property 15: PDF Total Calculation**
    - **Validates: Requirements 5.2, 5.3, 5.4, 5.5, 5.6, 5.7**

- [x] 6. Implement invoice upload view
  - [x] 6.1 Create invoice_upload_view
    - Add @login_required decorator
    - Check user access permissions (staff or shipment owner)
    - Verify no existing invoice (redirect with error if exists)
    - Handle GET request: render form
    - Handle POST request: validate and save uploaded file
    - Redirect to shipment detail on success
    - _Requirements: 1.2, 1.3, 1.8_
  
  - [ ]* 6.2 Write property test for invoice storage
    - **Property 2: Invoice Storage After Upload**
    - **Validates: Requirements 1.2**
  
  - [ ]* 6.3 Write property test for single invoice constraint
    - **Property 3: Single Invoice Constraint**
    - **Validates: Requirements 1.8**
  
  - [ ]* 6.4 Write unit tests for upload view
    - Test successful upload with valid PDF
    - Test successful upload with valid image
    - Test rejection of invalid file format
    - Test rejection when invoice already exists
    - Test permission enforcement
    - _Requirements: 1.1, 1.2, 1.4, 1.8_

- [-] 7. Implement invoice generation view
  - [ ] 7.1 Create invoice_generate_view
    - Add @login_required decorator
    - Check staff-only access (return 403 for non-staff)
    - Verify AWB number exists (redirect with error if missing)
    - Verify no existing invoice (redirect with error if exists)
    - Handle GET request: initialize form and formset
    - Handle POST request: validate forms, extract data, generate PDF
    - Save generated PDF to shipment.invoice field
    - Redirect to shipment detail on success
    - _Requirements: 4.1, 4.2, 4.3, 4.8, 4.9, 4.10, 4.11, 4.12, 4.13, 4.17, 4.19, 4.20, 4.21, 6.2, 7.1_
  
  - [ ]* 7.2 Write property test for shipper/consignee override isolation
    - **Property 10: Shipper/Consignee Override Isolation**
    - **Validates: Requirements 4.12, 4.13**
  
  - [ ]* 7.3 Write property test for line item support
    - **Property 11: Multiple Line Items Support**
    - **Validates: Requirements 4.17, 4.18**
  
  - [ ]* 7.4 Write property test for PDF generation and storage
    - **Property 12: PDF Generation and Storage**
    - **Validates: Requirements 4.19, 4.20, 5.1**
  
  - [ ]* 7.5 Write property test for line item non-persistence
    - **Property 13: Line Item Non-Persistence**
    - **Validates: Requirements 4.21**
  
  - [ ]* 7.6 Write property test for AWB prerequisite
    - **Property 16: AWB Prerequisite Enforcement**
    - **Validates: Requirements 6.2**
  
  - [ ]* 7.7 Write unit tests for generation view
    - Test successful generation with valid data
    - Test rejection without AWB number
    - Test rejection when invoice already exists
    - Test staff-only access enforcement
    - Test validation error handling
    - _Requirements: 4.1, 4.2, 4.3, 6.2, 7.1, 7.6_

- [ ] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement invoice deletion view
  - [x] 9.1 Create invoice_delete_view
    - Add @login_required decorator
    - Check user access permissions (staff or shipment owner)
    - Verify invoice exists (redirect with error if missing)
    - Check customer deletion permission (PENDING status only)
    - Handle GET request: render confirmation page
    - Handle POST request: delete file from storage, clear invoice field
    - Redirect to shipment detail on success
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_
  
  - [ ]* 9.2 Write property test for staff delete access
    - **Property 6: Staff Delete Access**
    - **Validates: Requirements 3.1**
  
  - [ ]* 9.3 Write property test for customer delete access
    - **Property 7: Customer Delete Access by Status**
    - **Validates: Requirements 3.3**
  
  - [ ]* 9.4 Write property test for deletion cleanup
    - **Property 8: Invoice Deletion Cleanup**
    - **Validates: Requirements 3.4, 3.5**
  
  - [ ]* 9.5 Write unit tests for deletion view
    - Test staff deletion from any status
    - Test customer deletion from PENDING status
    - Test customer deletion rejection from BOOKED status
    - Test file cleanup verification
    - Test permission enforcement
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 10. Implement invoice download view
  - [x] 10.1 Create invoice_download_view
    - Add @login_required decorator
    - Check user access permissions (staff or shipment owner)
    - Verify invoice exists (return 404 if missing)
    - Check customer download permission (BOOKED or later status)
    - Serve file using FileResponse with appropriate headers
    - _Requirements: 2.1, 2.2, 2.3, 2.4_
  
  - [ ]* 10.2 Write property test for customer download access
    - **Property 4: Customer Download Access by Status**
    - **Validates: Requirements 2.2, 2.3**
  
  - [ ]* 10.3 Write property test for file download
    - **Property 5: Invoice File Download**
    - **Validates: Requirements 2.4**
  
  - [ ]* 10.4 Write unit tests for download view
    - Test staff download from any status
    - Test customer download from BOOKED status
    - Test customer download rejection from PENDING status
    - Test file serving with correct headers
    - Test 404 when invoice missing
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [x] 11. Create invoice upload template
  - [x] 11.1 Create invoice_upload.html template
    - Extend base template
    - Display shipment AWB number
    - Render file upload form with CSRF token
    - Display field errors inline
    - Add help text for accepted formats and size limit
    - Add submit and cancel buttons
    - _Requirements: 1.1, 1.4_

- [x] 12. Create invoice generation template
  - [x] 12.1 Create invoice_generate.html template
    - Extend base template
    - Display shipment AWB number
    - Render shipper information fieldset (editable)
    - Render consignee information fieldset (editable)
    - Render AWB number field (read-only with help text)
    - Render product line items formset with management form
    - Add JavaScript for dynamic formset management (add/remove items)
    - Display field errors inline
    - Add submit and cancel buttons
    - _Requirements: 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11, 4.14, 4.15, 4.16, 4.17, 4.18_

- [x] 13. Create invoice deletion confirmation template
  - [x] 13.1 Create invoice_delete_confirm.html template
    - Extend base template
    - Display shipment AWB number
    - Show warning message about permanent deletion
    - Display invoice filename
    - Render confirmation form with CSRF token
    - Add confirm and cancel buttons
    - _Requirements: 3.4, 3.5_

- [x] 14. Update shipment detail template with invoice section
  - [x] 14.1 Add invoice section to shipment_detail.html
    - Add "Invoice" section heading
    - Implement template logic for invoice existence check
    - When invoice exists: display filename, download button, preview button, delete button
    - When no invoice exists: display "No invoice attached" message, upload button, "Create Invoice" button
    - Implement staff vs customer permission checks using {% if request.user.is_staff %}
    - Implement status-based permission checks for download (BOOKED or later for customers)
    - Implement status-based permission checks for delete (PENDING only for customers)
    - Hide "Create Invoice" button when no AWB number exists
    - Hide upload and generation options when invoice exists
    - _Requirements: 1.5, 1.6, 1.7, 1.8, 2.1, 2.2, 2.3, 2.5, 3.1, 3.2, 3.3, 3.6, 4.1, 4.2, 4.3, 6.1, 6.3, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8, 8.9, 8.10, 8.11_

- [x] 15. Configure URL patterns
  - [x] 15.1 Add invoice URL patterns to exportimport/urls.py
    - Add invoice_upload URL pattern
    - Add invoice_generate URL pattern
    - Add invoice_delete URL pattern
    - Add invoice_download URL pattern
    - Use shipment_id as URL parameter for all patterns
    - _Requirements: All view-related requirements_

- [ ] 16. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 17. Create Hypothesis test strategies
  - [ ] 17.1 Create test data generation strategies
    - Implement shipment_strategy for random shipments
    - Implement shipment_with_awb_strategy for booked shipments
    - Implement shipment_without_awb_strategy for pending shipments
    - Implement shipment_with_invoice_strategy for shipments with invoices
    - Implement line_item_strategy for valid line items
    - Implement invalid_line_item_strategy for validation testing
    - _Requirements: All property test requirements_

- [ ]* 18. Write integration tests
  - [ ]* 18.1 Test complete upload workflow
    - Create shipment → Upload invoice → View invoice → Delete invoice
    - _Requirements: 1.2, 1.3, 2.4, 3.4, 3.5_
  
  - [ ]* 18.2 Test complete generation workflow
    - Create shipment → Book shipment → Generate invoice → Download invoice
    - _Requirements: 4.19, 4.20, 5.1, 2.4, 6.2_
  
  - [ ]* 18.3 Test permission workflows
    - Test all permission scenarios across staff/customer and shipment statuses
    - _Requirements: 2.1, 2.2, 2.3, 3.1, 3.2, 3.3, 4.3, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_
  
  - [ ]* 18.4 Test error recovery scenarios
    - Test system behavior after file upload failures
    - Test system behavior after PDF generation failures
    - Test system behavior after deletion failures
    - _Requirements: All error handling requirements_

- [ ] 19. Final checkpoint - Complete system verification
  - Run full test suite with coverage report
  - Verify all property tests pass with 100+ iterations
  - Verify 90%+ code coverage for invoice-related code
  - Test all UI flows manually in development environment
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation throughout implementation
- Property tests validate universal correctness properties with 100+ iterations
- Unit tests validate specific examples and edge cases
- The design uses Python/Django, so all code should follow Django best practices
- Template-based permission enforcement means no view-level permission decorators beyond @login_required
- Product line items are temporary and never persisted to the database
- Single invoice constraint is enforced at the view level before any file operations
