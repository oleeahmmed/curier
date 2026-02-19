"""
Services for bag management operations including PDF generation.
"""
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors


class AirInvoicePDFGenerator:
    """
    Generates multi-page A4 PDF air invoices for sealed bags.
    Each page represents one parcel and matches the airinvoice.html template format.
    """
    
    def __init__(self, bag):
        self.bag = bag
        self.buffer = BytesIO()
        self.page_width, self.page_height = A4
        
    def generate(self):
        """
        Generate the complete multi-page PDF with one page per parcel.
        Returns: tuple (pdf_content, page_count)
        """
        # Create the PDF document
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=40,
            bottomMargin=40
        )
        
        # Build story (content) for all pages
        story = []
        shipments = self.bag.shipment.all()
        
        for idx, shipment in enumerate(shipments):
            # Add page content for this shipment
            story.extend(self._build_page_content(shipment))
            
            # Add page break if not the last page
            if idx < len(shipments) - 1:
                from reportlab.platypus import PageBreak
                story.append(PageBreak())
        
        # Build the PDF
        doc.build(story)
        
        # Get the PDF content
        pdf_content = self.buffer.getvalue()
        self.buffer.close()
        
        return pdf_content, len(shipments)
    
    def _build_page_content(self, shipment):
        """
        Build content for a single page (one parcel).
        Matches the airinvoice.html template format.
        """
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        header_style = ParagraphStyle(
            'HeaderBox',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=6
        )
        
        info_style = ParagraphStyle(
            'InfoText',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        info_left_style = ParagraphStyle(
            'InfoTextLeft',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=10
        )
        
        title_style = ParagraphStyle(
            'MainTitle',
            parent=styles['Normal'],
            fontSize=12,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        # Header section with shipper and consignee
        header_data = [
            [
                self._build_shipper_section(header_style, info_left_style),
                self._build_consignee_section(shipment, header_style, info_left_style)
            ]
        ]
        
        header_table = Table(header_data, colWidths=[240, 240])
        header_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        story.append(header_table)
        story.append(Spacer(1, 20))
        
        # Main title
        story.append(Paragraph("INVOICE and PACKING LIST", title_style))
        story.append(Spacer(1, 10))
        
        # Goods table
        goods_table = self._build_goods_table(shipment)
        story.append(goods_table)
        story.append(Spacer(1, 20))
        
        # Footer section
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=5
        )
        
        awb_style = ParagraphStyle(
            'AWB',
            parent=styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        )
        
        story.append(Paragraph("NO COMMERCIAL INVOICE VALUE", footer_style))
        story.append(Paragraph(f"AWB# {shipment.awb_number}", awb_style))
        
        return story
    
    def _build_shipper_section(self, header_style, info_style):
        """Build shipper information section."""
        content = []
        
        # Create a bordered box style for headers
        box_style = ParagraphStyle(
            'BoxHeader',
            parent=header_style,
            borderWidth=1,
            borderColor=colors.black,
            borderPadding=3,
            alignment=TA_CENTER
        )
        
        # Shipper name header
        content.append(Paragraph("<b>SHIPPER NAME</b>", box_style))
        content.append(Spacer(1, 6))
        
        # Shipper name
        content.append(Paragraph("RR HONG KONG LTD", info_style))
        content.append(Spacer(1, 10))
        
        # Address header
        content.append(Paragraph("<b>ADDRESS</b>", box_style))
        content.append(Spacer(1, 6))
        
        # Address
        content.append(Paragraph("HONG KONG", info_style))
        
        return content
    
    def _build_consignee_section(self, shipment, header_style, info_style):
        """Build consignee information section from shipment data."""
        content = []
        
        # Create a bordered box style for headers
        box_style = ParagraphStyle(
            'BoxHeader',
            parent=header_style,
            borderWidth=1,
            borderColor=colors.black,
            borderPadding=3,
            alignment=TA_CENTER
        )
        
        # Consignee name header
        content.append(Paragraph("<b>CONSIGNEE NAME</b>", box_style))
        content.append(Spacer(1, 6))
        
        # Consignee name
        consignee_name = shipment.recipient_name or "N/A"
        content.append(Paragraph(consignee_name, info_style))
        content.append(Spacer(1, 10))
        
        # Address header
        content.append(Paragraph("<b>ADDRESS</b>", box_style))
        content.append(Spacer(1, 6))
        
        # Address details
        address_lines = []
        if shipment.recipient_address:
            address_lines.append(shipment.recipient_address)
        if shipment.recipient_country:
            address_lines.append(shipment.recipient_country)
        if shipment.recipient_phone:
            address_lines.append(f"TEL NO. {shipment.recipient_phone}")
        
        address_text = "<br/>".join(address_lines) if address_lines else "N/A"
        content.append(Paragraph(address_text, info_style))
        
        return content
    
    def _build_goods_table(self, shipment):
        """Build the goods description table."""
        # Table headers
        headers = [
            'DESCRIPTION OF GOODS',
            'WEIGHT\n(KG)',
            'QUANTITY',
            'VALUE'
        ]
        
        # Content row
        description = shipment.contents or "N/A"
        weight = f"{shipment.weight_estimated}kg" if shipment.weight_estimated else "N/A"
        quantity = "1pcs"  # Default to 1 piece
        value = f"{shipment.declared_currency} {shipment.declared_value}" if shipment.declared_value else "N/A"
        
        content_row = [description, weight, quantity, value]
        
        # Total row
        total_row = ['', '', '', value]
        
        # Build table data
        table_data = [headers, content_row, total_row]
        
        # Column widths (proportional to A4 width)
        col_widths = [200, 80, 80, 80]
        
        # Create table
        table = Table(table_data, colWidths=col_widths, rowHeights=[40, 100, 30])
        
        # Table styling
        table.setStyle(TableStyle([
            # Headers
            ('BACKGROUND', (0, 0), (-1, 0), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Content row
            ('ALIGN', (0, 1), (0, 1), 'LEFT'),  # Description left-aligned
            ('ALIGN', (1, 1), (-1, 1), 'CENTER'),  # Others centered
            ('VALIGN', (0, 1), (-1, 1), 'MIDDLE'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, 1), 10),
            ('LEFTPADDING', (0, 1), (0, 1), 10),
            
            # Total row
            ('ALIGN', (0, 2), (-1, 2), 'CENTER'),
            ('VALIGN', (0, 2), (-1, 2), 'MIDDLE'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 2), (-1, 2), 10),
            
            # Borders
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            
            # Special styling for total row borders
            ('LINEBELOW', (0, 1), (-1, 1), 1, colors.black),
        ]))
        
        return table


class ManifestPDFGenerator:
    """
    Generate PDF export for manifest using ReportLab.
    Follows the format specified in manifast.html template.
    """
    
    def __init__(self, manifest):
        """
        Initialize generator with manifest instance.
        
        Args:
            manifest: Manifest instance to generate PDF for
        """
        self.manifest = manifest
        self.buffer = BytesIO()
        self.page_width, self.page_height = A4
    
    def generate(self):
        """
        Generate the PDF document.
        
        Returns:
            bytes: PDF content
        """
        # Create the PDF document
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30
        )
        
        # Build story (content)
        story = []
        
        # Add header
        story.extend(self._build_header())
        story.append(Spacer(1, 15))
        
        # Add meta section
        story.extend(self._build_meta_section())
        story.append(Spacer(1, 15))
        
        # Add shipments table
        story.append(self._build_shipments_table())
        story.append(Spacer(1, 10))
        
        # Add footer
        story.extend(self._build_footer())
        
        # Build the PDF
        doc.build(story)
        
        # Get the PDF content
        pdf_content = self.buffer.getvalue()
        self.buffer.close()
        
        return pdf_content
    
    def _build_header(self):
        """Build header section with company name and title."""
        styles = getSampleStyleSheet()
        
        # Company name style
        company_style = ParagraphStyle(
            'CompanyName',
            parent=styles['Normal'],
            fontSize=16,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=5
        )
        
        # Title style
        title_style = ParagraphStyle(
            'ManifestTitle',
            parent=styles['Normal'],
            fontSize=14,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            spaceAfter=10
        )
        
        content = []
        content.append(Paragraph("Fast Line Express BD", company_style))
        content.append(Paragraph("New Shahi Packaging & Poly Industries Ltd", company_style))
        content.append(Paragraph("MANIFEST", title_style))
        
        return content
    
    def _build_meta_section(self):
        """Build meta information section."""
        styles = getSampleStyleSheet()
        
        meta_style = ParagraphStyle(
            'MetaInfo',
            parent=styles['Normal'],
            fontSize=10,
            alignment=TA_LEFT,
            spaceAfter=3
        )
        
        content = []
        
        # Format departure date
        departure_date_str = self.manifest.departure_date.strftime('%d/%m/%Y') if self.manifest.departure_date else 'N/A'
        
        # Create meta information table for better layout
        meta_data = [
            [
                Paragraph("<b>Agent Name:</b> FAST LINE (DAC)", meta_style),
                Paragraph(f"<b>Flight No.:</b> {self.manifest.flight_number or 'N/A'}", meta_style)
            ],
            [
                Paragraph(f"<b>MAWB:</b> {self.manifest.mawb_number or 'N/A'}", meta_style),
                Paragraph(f"<b>Flight Date:</b> {departure_date_str}", meta_style)
            ]
        ]
        
        meta_table = Table(meta_data, colWidths=[270, 270])
        meta_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        
        content.append(meta_table)
        
        return content
    
    def _build_shipments_table(self):
        """
        Build main table with all shipments.
        
        Columns:
        - No. (sequential number)
        - AWB No
        - Shipper (from shipment.sender_name)
        - Consignee (recipient_name + address, multi-line)
        - Origin/Dest
        - PCS (pieces, default 1)
        - Weight (in KG)
        - Description (contents)
        - Currency Value Code
        - Remark
        - COD (if is_cod)
        - Bag no
        """
        # Table headers
        headers = [
            'No.', 'AWB No', 'Shipper', 'Consignee', 'Origin/Dest',
            'PCS', 'Weight', 'Description', 'Value/Code', 'Remark', 'COD', 'Bag No'
        ]
        
        # Build table data
        table_data = [headers]
        
        # Iterate through all bags and shipments
        shipment_number = 1
        for bag in self.manifest.bags.all():
            for shipment in bag.shipment.all():
                # Format consignee with multi-line address
                consignee_lines = [shipment.recipient_name or 'N/A']
                if shipment.recipient_address:
                    consignee_lines.append(shipment.recipient_address)
                consignee_text = '<br/>'.join(consignee_lines)
                
                # Format weight
                weight_str = f"{shipment.weight_estimated}" if shipment.weight_estimated else "0"
                
                # Format value/code
                value_code = f"{shipment.declared_value} ({shipment.declared_currency})" if shipment.declared_value else "N/A"
                
                # COD indicator
                cod_indicator = "COD" if shipment.is_cod else ""
                
                # Origin/Dest - using sender and recipient countries
                origin_dest = f"{shipment.sender_country[:3].upper()} / {shipment.recipient_country[:3].upper()}"
                
                row = [
                    str(shipment_number),
                    shipment.awb_number or 'N/A',
                    shipment.sender_name or 'N/A',
                    Paragraph(consignee_text, getSampleStyleSheet()['Normal']),
                    origin_dest,
                    '1',  # Default to 1 piece
                    weight_str,
                    shipment.contents or 'N/A',
                    value_code,
                    '',  # Remark - empty for now
                    cod_indicator,
                    bag.bag_number
                ]
                
                table_data.append(row)
                shipment_number += 1
        
        # Column widths (adjusted to fit A4 width)
        col_widths = [25, 60, 70, 80, 50, 30, 40, 60, 50, 40, 30, 50]
        
        # Create table
        table = Table(table_data, colWidths=col_widths)
        
        # Table styling
        table.setStyle(TableStyle([
            # Headers
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('VALIGN', (0, 0), (-1, 0), 'MIDDLE'),
            
            # Content rows
            ('ALIGN', (0, 1), (0, -1), 'CENTER'),  # No. column centered
            ('ALIGN', (1, 1), (2, -1), 'LEFT'),    # AWB, Shipper left-aligned
            ('ALIGN', (3, 1), (3, -1), 'LEFT'),    # Consignee left-aligned
            ('ALIGN', (4, 1), (-1, -1), 'CENTER'), # Rest centered
            ('VALIGN', (0, 1), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            
            # Borders
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('BOX', (0, 0), (-1, -1), 1, colors.black),
            
            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        
        return table
    
    def _build_footer(self):
        """Build footer with totals."""
        styles = getSampleStyleSheet()
        
        footer_style = ParagraphStyle(
            'FooterText',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT,
            spaceAfter=3
        )
        
        content = []
        
        # Calculate totals
        total_shipments = self.manifest.total_parcels
        total_pcs = total_shipments  # Assuming 1 piece per shipment
        total_weight = self.manifest.total_weight
        
        # Create footer text
        footer_text = f"TOTAL SHIPMENTS: {total_shipments} &nbsp;&nbsp;&nbsp; PCS: {total_pcs} &nbsp;&nbsp;&nbsp; WEIGHT: {total_weight} KGS"
        
        content.append(Paragraph(footer_text, footer_style))
        
        return content


def generate_air_invoice_for_bag(bag, user):
    """
    Generate air invoice PDF for a sealed bag.
    
    Args:
        bag: Bag instance
        user: User who is generating the invoice
        
    Returns:
        AirInvoice instance with generated PDF
    """
    from .models import AirInvoice
    
    # Generate invoice number
    date_str = timezone.now().strftime('%Y%m%d')
    invoice_number = f"INV-{bag.bag_number}-{date_str}"
    
    # Generate PDF
    generator = AirInvoicePDFGenerator(bag)
    pdf_content, page_count = generator.generate()
    
    # Create or update AirInvoice record
    air_invoice, created = AirInvoice.objects.get_or_create(
        bag=bag,
        defaults={
            'invoice_number': invoice_number,
            'page_count': page_count,
            'generated_by': user
        }
    )
    
    if not created:
        # Update existing invoice
        air_invoice.invoice_number = invoice_number
        air_invoice.page_count = page_count
        air_invoice.generated_by = user
    
    # Save PDF file
    filename = f"AIR_INVOICE_{bag.bag_number}_{date_str}.pdf"
    air_invoice.pdf_file.save(filename, ContentFile(pdf_content), save=True)
    
    return air_invoice


class ManifestExcelGenerator:
    """
    Generate Excel export for manifest using openpyxl.
    Same structure as PDF but in Excel format.
    """
    
    def __init__(self, manifest):
        """
        Initialize generator with manifest instance.
        
        Args:
            manifest: Manifest instance to generate Excel for
        """
        self.manifest = manifest
        self.workbook = None
        self.worksheet = None
    
    def generate(self):
        """
        Generate the Excel document.
        
        Returns:
            bytes: Excel content
        """
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, Border, Side
        
        # Create workbook and worksheet
        self.workbook = Workbook()
        self.worksheet = self.workbook.active
        self.worksheet.title = "Manifest"
        
        # Current row tracker
        self.current_row = 1
        
        # Build Excel content
        self._write_header()
        self._write_meta_info()
        self._write_column_headers()
        self._write_shipment_rows()
        self._write_totals_row()
        self._apply_formatting()
        
        # Save to BytesIO
        buffer = BytesIO()
        self.workbook.save(buffer)
        excel_content = buffer.getvalue()
        buffer.close()
        
        return excel_content
    
    def _write_header(self):
        """Write header section."""
        from openpyxl.styles import Font, Alignment
        
        # Write company name in first row
        self.worksheet.cell(row=self.current_row, column=1, value="Fast Line Express BD")
        self.worksheet.cell(row=self.current_row, column=1).font = Font(size=16, bold=True)
        self.worksheet.cell(row=self.current_row, column=1).alignment = Alignment(horizontal='center')
        self.current_row += 1
        
        # Write company details
        self.worksheet.cell(row=self.current_row, column=1, value="New Shahi Packaging & Poly Industries Ltd")
        self.worksheet.cell(row=self.current_row, column=1).font = Font(size=12, bold=True)
        self.worksheet.cell(row=self.current_row, column=1).alignment = Alignment(horizontal='center')
        self.worksheet.merge_cells(start_row=self.current_row, start_column=1, end_row=self.current_row, end_column=12)
        self.current_row += 1
        
        # Write "MANIFEST" in second row
        self.worksheet.cell(row=self.current_row, column=1, value="MANIFEST")
        self.worksheet.cell(row=self.current_row, column=1).font = Font(size=14, bold=True)
        self.worksheet.cell(row=self.current_row, column=1).alignment = Alignment(horizontal='center')
        self.worksheet.merge_cells(start_row=self.current_row, start_column=1, end_row=self.current_row, end_column=12)
        self.current_row += 1
        
        # Add blank row
        self.current_row += 1
    
    def _write_meta_info(self):
        """Write meta information."""
        from openpyxl.styles import Font
        
        # Format departure date
        departure_date_str = self.manifest.departure_date.strftime('%d/%m/%Y') if self.manifest.departure_date else 'N/A'
        
        # Write Agent Name and Flight No
        self.worksheet.cell(row=self.current_row, column=1, value="Agent Name:")
        self.worksheet.cell(row=self.current_row, column=1).font = Font(bold=True)
        self.worksheet.cell(row=self.current_row, column=2, value="FAST LINE (DAC)")
        
        self.worksheet.cell(row=self.current_row, column=4, value="Flight No.:")
        self.worksheet.cell(row=self.current_row, column=4).font = Font(bold=True)
        self.worksheet.cell(row=self.current_row, column=5, value=self.manifest.flight_number or 'N/A')
        self.current_row += 1
        
        # Write MAWB and Flight Date
        self.worksheet.cell(row=self.current_row, column=1, value="MAWB:")
        self.worksheet.cell(row=self.current_row, column=1).font = Font(bold=True)
        self.worksheet.cell(row=self.current_row, column=2, value=self.manifest.mawb_number or 'N/A')
        
        self.worksheet.cell(row=self.current_row, column=4, value="Flight Date:")
        self.worksheet.cell(row=self.current_row, column=4).font = Font(bold=True)
        self.worksheet.cell(row=self.current_row, column=5, value=departure_date_str)
        self.current_row += 1
        
        # Add blank row
        self.current_row += 1
    
    def _write_column_headers(self):
        """Write table column headers."""
        from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
        
        # Column headers
        headers = [
            'No.', 'AWB No', 'Shipper', 'Consignee', 'Origin/Dest',
            'PCS', 'Weight', 'Description', 'Value/Code', 'Remark', 'COD', 'Bag No'
        ]
        
        # Write headers
        for col_idx, header in enumerate(headers, start=1):
            cell = self.worksheet.cell(row=self.current_row, column=col_idx, value=header)
            cell.font = Font(bold=True, size=10)
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            cell.fill = PatternFill(start_color='D3D3D3', end_color='D3D3D3', fill_type='solid')
        
        self.current_row += 1
    
    def _write_shipment_rows(self):
        """Write all shipment data rows."""
        from openpyxl.styles import Alignment
        
        # Iterate through all bags and shipments
        shipment_number = 1
        for bag in self.manifest.bags.all():
            for shipment in bag.shipment.all():
                # Format consignee with multi-line address
                consignee_lines = [shipment.recipient_name or 'N/A']
                if shipment.recipient_address:
                    consignee_lines.append(shipment.recipient_address)
                consignee_text = '\n'.join(consignee_lines)
                
                # Format weight
                weight_str = f"{shipment.weight_estimated}" if shipment.weight_estimated else "0"
                
                # Format value/code
                value_code = f"{shipment.declared_value} ({shipment.declared_currency})" if shipment.declared_value else "N/A"
                
                # COD indicator
                cod_indicator = "COD" if shipment.is_cod else ""
                
                # Origin/Dest - using sender and recipient countries
                origin_dest = f"{shipment.sender_country[:3].upper()} / {shipment.recipient_country[:3].upper()}"
                
                # Write row data
                row_data = [
                    shipment_number,
                    shipment.awb_number or 'N/A',
                    shipment.sender_name or 'N/A',
                    consignee_text,
                    origin_dest,
                    1,  # Default to 1 piece
                    weight_str,
                    shipment.contents or 'N/A',
                    value_code,
                    '',  # Remark - empty for now
                    cod_indicator,
                    bag.bag_number
                ]
                
                for col_idx, value in enumerate(row_data, start=1):
                    cell = self.worksheet.cell(row=self.current_row, column=col_idx, value=value)
                    
                    # Set alignment based on column
                    if col_idx == 1:  # No. column
                        cell.alignment = Alignment(horizontal='center', vertical='top')
                    elif col_idx in [2, 3]:  # AWB, Shipper
                        cell.alignment = Alignment(horizontal='left', vertical='top')
                    elif col_idx == 4:  # Consignee
                        cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
                    else:  # Rest
                        cell.alignment = Alignment(horizontal='center', vertical='top')
                
                self.current_row += 1
                shipment_number += 1
    
    def _write_totals_row(self):
        """Write totals row at bottom."""
        from openpyxl.styles import Font, Alignment
        
        # Add blank row before totals
        self.current_row += 1
        
        # Calculate totals
        total_shipments = self.manifest.total_parcels
        total_pcs = total_shipments  # Assuming 1 piece per shipment
        total_weight = self.manifest.total_weight
        
        # Write totals text
        totals_text = f"TOTAL SHIPMENTS: {total_shipments}     PCS: {total_pcs}     WEIGHT: {total_weight} KGS"
        self.worksheet.cell(row=self.current_row, column=1, value=totals_text)
        self.worksheet.cell(row=self.current_row, column=1).font = Font(bold=True, size=10)
        self.worksheet.cell(row=self.current_row, column=1).alignment = Alignment(horizontal='left')
        self.worksheet.merge_cells(start_row=self.current_row, start_column=1, end_row=self.current_row, end_column=12)
    
    def _apply_formatting(self):
        """Apply cell formatting and styling."""
        from openpyxl.styles import Border, Side
        from openpyxl.utils import get_column_letter
        
        # Set column widths
        column_widths = {
            1: 6,   # No.
            2: 15,  # AWB No
            3: 18,  # Shipper
            4: 25,  # Consignee
            5: 12,  # Origin/Dest
            6: 6,   # PCS
            7: 10,  # Weight
            8: 20,  # Description
            9: 15,  # Value/Code
            10: 12, # Remark
            11: 6,  # COD
            12: 15  # Bag No
        }
        
        for col_idx, width in column_widths.items():
            column_letter = get_column_letter(col_idx)
            self.worksheet.column_dimensions[column_letter].width = width
        
        # Add borders to data table (from column headers to last shipment row)
        # Find the header row (should be row 7 based on structure)
        header_row = 7
        last_data_row = self.current_row - 2  # Exclude blank row and totals row
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Apply borders to all cells in the table
        for row in range(header_row, last_data_row + 1):
            for col in range(1, 13):  # 12 columns
                self.worksheet.cell(row=row, column=col).border = thin_border



class ManifestFinalizationService:
    """
    Handle the complete manifest finalization workflow.
    Encapsulates all operations that must happen atomically.
    """
    
    def __init__(self, manifest, user):
        """
        Initialize service.
        
        Args:
            manifest: Manifest instance to finalize
            user: User performing the finalization
        """
        self.manifest = manifest
        self.user = user
    
    def _validate_can_finalize(self):
        """
        Validate manifest is in correct state for finalization.
        
        Raises:
            ValidationError: If manifest cannot be finalized
        """
        from django.core.exceptions import ValidationError
        
        if self.manifest.status != 'DRAFT':
            raise ValidationError("Only DRAFT manifests can be finalized")
        
        if self.manifest.bags.count() == 0:
            raise ValidationError("Manifest must have at least one bag")
    
    def _update_manifest_status(self):
        """Update manifest to FINALIZED status."""
        self.manifest.status = 'FINALIZED'
        self.manifest.finalized_by = self.user
        self.manifest.finalized_at = timezone.now()
        self.manifest.save()
    
    def _update_bags(self):
        """Update all bags to IN_MANIFEST status."""
        for bag in self.manifest.bags.all():
            bag.status = 'IN_MANIFEST'
            bag.save()
    
    def _update_shipments(self):
        """Update all shipments to IN_EXPORT_MANIFEST status."""
        for bag in self.manifest.bags.all():
            for shipment in bag.shipment.all():
                shipment.current_status = 'IN_EXPORT_MANIFEST'
                shipment.save()
    
    def _create_tracking_events(self):
        """Create tracking events for all shipments."""
        from .models import TrackingEvent
        
        for bag in self.manifest.bags.all():
            for shipment in bag.shipment.all():
                TrackingEvent.objects.create(
                    shipment=shipment,
                    status='IN_EXPORT_MANIFEST',
                    description=f"Added to manifest {self.manifest.manifest_number}",
                    location='Bangladesh Warehouse',
                    updated_by=self.user
                )
    
    def _generate_exports(self):
        """
        Generate PDF and Excel exports.
        
        Returns:
            tuple: (pdf_bytes, excel_bytes)
        """
        # Generate PDF
        pdf_generator = ManifestPDFGenerator(self.manifest)
        pdf_bytes = pdf_generator.generate()
        
        # Generate Excel
        excel_generator = ManifestExcelGenerator(self.manifest)
        excel_bytes = excel_generator.generate()
        
        return (pdf_bytes, excel_bytes)
    
    def _store_exports(self, pdf_content, excel_content):
        """
        Store exports in ManifestExport model.
        
        Args:
            pdf_content: PDF bytes
            excel_content: Excel bytes
        """
        from .models import ManifestExport
        
        # Create ManifestExport instance
        manifest_export = ManifestExport(
            manifest=self.manifest,
            generated_by=self.user
        )
        
        # Save PDF file
        pdf_filename = f"MANIFEST_{self.manifest.manifest_number}.pdf"
        manifest_export.pdf_file.save(pdf_filename, ContentFile(pdf_content), save=False)
        
        # Save Excel file
        excel_filename = f"MANIFEST_{self.manifest.manifest_number}.xlsx"
        manifest_export.excel_file.save(excel_filename, ContentFile(excel_content), save=False)
        
        # Save the ManifestExport instance
        manifest_export.save()
    
    def finalize(self):
        """
        Execute the complete finalization workflow.
        
        Returns:
            tuple: (pdf_content, excel_content)
        
        Raises:
            ValidationError: If manifest cannot be finalized
        """
        from django.db import transaction
        
        # Wrap all operations in database transaction
        with transaction.atomic():
            # Validate manifest can be finalized
            self._validate_can_finalize()
            
            # Update manifest status
            self._update_manifest_status()
            
            # Update all bags
            self._update_bags()
            
            # Update all shipments
            self._update_shipments()
            
            # Create tracking events
            self._create_tracking_events()
            
            # Generate exports
            pdf_content, excel_content = self._generate_exports()
            
            # Store exports
            self._store_exports(pdf_content, excel_content)
        
        # Return export content
        return (pdf_content, excel_content)



class ManifestStatusUpdateService:
    """
    Handle manifest status updates with cascading changes.
    """
    
    def __init__(self, manifest, user):
        """
        Initialize service.
        
        Args:
            manifest: Manifest instance to update
            user: User performing the update
        """
        self.manifest = manifest
        self.user = user
    
    def update_to_departed(self):
        """
        Update manifest and all related entities to DEPARTED status.
        
        Operations:
        1. Update manifest status to DEPARTED
        2. Update all bags to DISPATCHED
        3. Update all shipments to HANDED_TO_AIRLINE
        4. Create tracking events
        """
        from django.db import transaction
        from .models import TrackingEvent
        
        with transaction.atomic():
            # Update manifest status
            self.manifest.status = 'DEPARTED'
            self.manifest.save()
            
            # Update all bags to DISPATCHED
            for bag in self.manifest.bags.all():
                bag.status = 'DISPATCHED'
                bag.save()
            
            # Update all shipments to HANDED_TO_AIRLINE and create tracking events
            for bag in self.manifest.bags.all():
                for shipment in bag.shipment.all():
                    shipment.current_status = 'HANDED_TO_AIRLINE'
                    shipment.save()
                    
                    # Create tracking event
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        status='HANDED_TO_AIRLINE',
                        description=f"Departed on flight {self.manifest.flight_number}",
                        location='Bangladesh Airport',
                        updated_by=self.user
                    )
    
    def update_to_in_transit(self):
        """
        Update all shipments to IN_TRANSIT_TO_HK status.
        
        Operations:
        1. Update all shipments to IN_TRANSIT_TO_HK
        2. Create tracking events
        """
        from django.db import transaction
        from .models import TrackingEvent
        
        with transaction.atomic():
            # Update all shipments to IN_TRANSIT_TO_HK and create tracking events
            for bag in self.manifest.bags.all():
                for shipment in bag.shipment.all():
                    shipment.current_status = 'IN_TRANSIT_TO_HK'
                    shipment.save()
                    
                    # Create tracking event
                    TrackingEvent.objects.create(
                        shipment=shipment,
                        status='IN_TRANSIT_TO_HK',
                        description="In transit to Hong Kong",
                        location='In Transit',
                        updated_by=self.user
                    )
