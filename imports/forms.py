from django import forms


MAX_UPLOAD_BYTES = 50 * 1024 * 1024


class HRISUploadForm(forms.Form):
    csv_file = forms.FileField(
        label="HRIS CSV file",
        help_text="UTF-8 CSV, up to 50 MB. The file is analyzed and then discarded.",
        widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}),
    )

    def clean_csv_file(self):
        uploaded_file = self.cleaned_data["csv_file"]
        if uploaded_file.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError("The CSV must be 50 MB or smaller.")
        return uploaded_file
