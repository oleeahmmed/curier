from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Customer


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
