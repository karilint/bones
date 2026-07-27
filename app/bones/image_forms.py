from django import forms
from django.core.exceptions import ValidationError
from PIL import Image


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        clean_one = super().clean
        if isinstance(data, (list, tuple)):
            return [clean_one(item, initial) for item in data]
        return [clean_one(data, initial)]


class EntityImageUploadForm(forms.Form):
    images = MultipleFileField(widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "class": "w3-input w3-border"}))
    alt_text = forms.CharField(required=False, max_length=300, widget=forms.TextInput(attrs={"class": "w3-input w3-border"}))

    def clean_images(self):
        uploads = self.cleaned_data["images"]
        for upload in uploads:
            if upload.size > 20 * 1024 * 1024:
                raise ValidationError("Images must be 20 MB or smaller.")
            try:
                image = Image.open(upload)
                image.verify()
            except Exception as exc:
                raise ValidationError("Upload valid JPEG, PNG, or WebP images.") from exc
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValidationError("Only JPEG, PNG, and WebP images are supported.")
            upload.seek(0)
        return uploads