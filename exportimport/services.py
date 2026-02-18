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
