from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Customer, Shipment


class CustomerRegistrationForm(forms.ModelForm):
    """
    Registration form with User and Customer fields.
    """
    full_name = forms.CharField(max_length=200, required=True)
    email = forms.EmailField(required=True)
    country = forms.CharField(max_length=100, initial='Bangladesh')
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    
    class Meta:
        model = User
        fields = ['username', 'email']
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError('Username already exists')
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password and password != confirm_password:
            raise ValidationError('Passwords do not match')
        
        return cleaned_data


class ProfileForm(forms.ModelForm):
    """
    Profile update form for Customer model fields.
    """
    class Meta:
        model = Customer
        fields = ['name', 'email', 'phone', 'address', 'country']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and '@' not in email:
            raise ValidationError('Enter a valid email address')
        return email


class PasswordChangeForm(forms.Form):
    """
    Password change form with old password verification.
    """
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password = forms.CharField(widget=forms.PasswordInput)
    confirm_new_password = forms.CharField(widget=forms.PasswordInput)
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
    
    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not self.user.check_password(old_password):
            raise ValidationError('Old password is incorrect')
        return old_password
    
    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_new_password = cleaned_data.get('confirm_new_password')
        
        if new_password and confirm_new_password and new_password != confirm_new_password:
            raise ValidationError('New passwords do not match')
        
        return cleaned_data


# Commercial Invoice Forms

class InvoiceUploadForm(forms.ModelForm):
    """
    Form for uploading invoice files to a shipment.
    Validates file extension (PDF, JPG, JPEG, PNG) and size (max 10MB).
    """
    class Meta:
        model = Shipment
        fields = ['invoice']
    
    def clean_invoice(self):
        invoice = self.cleaned_data.get('invoice')
        
        if invoice:
            # Validate file extension
            ext = invoice.name.split('.')[-1].lower()
            if ext not in ['pdf', 'jpg', 'jpeg', 'png']:
                raise ValidationError('Only PDF and image files (PDF, JPG, JPEG, PNG) are allowed')
            
            # Validate file size (10MB max)
            if invoice.size > 10 * 1024 * 1024:
                raise ValidationError('File size must not exceed 10MB')
        
        return invoice


class InvoiceGenerationForm(forms.Form):
    """
    Form for generating invoices with product line items.
    Pre-populates shipper/consignee information from shipment but allows editing.
    AWB number is read-only.
    """
    # Shipper information (editable, pre-populated from shipment)
    shipper_name = forms.CharField(max_length=200, required=True)
    shipper_address = forms.CharField(widget=forms.Textarea, required=True)
    
    # Consignee information (editable, pre-populated from shipment)
    consignee_name = forms.CharField(max_length=200, required=True)
    consignee_address = forms.CharField(widget=forms.Textarea, required=True)
    
    # AWB (read-only, populated from shipment)
    awb_number = forms.CharField(max_length=50, disabled=True, required=False)
    
    def __init__(self, shipment, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Pre-populate from shipment
        self.fields['shipper_name'].initial = shipment.shipper_name
        self.fields['shipper_address'].initial = shipment.shipper_address
        self.fields['consignee_name'].initial = shipment.recipient_name
        self.fields['consignee_address'].initial = shipment.recipient_address
        self.fields['awb_number'].initial = shipment.awb_number


class ProductLineItemForm(forms.Form):
    """
    Form for individual product line items in invoice generation.
    All numeric fields have min_value constraints to ensure positive values.
    """
    description = forms.CharField(max_length=500, required=True)
    weight = forms.DecimalField(
        max_digits=6, 
        decimal_places=2, 
        min_value=0.01, 
        required=True,
        help_text="Weight in kg"
    )
    quantity = forms.IntegerField(min_value=1, required=True)
    unit_value = forms.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        min_value=0.01, 
        required=True,
        help_text="Unit value in declared currency"
    )


# Dynamic formset for multiple line items
ProductLineItemFormSet = forms.formset_factory(
    ProductLineItemForm,
    extra=1,
    min_num=1,
    validate_min=True
)
