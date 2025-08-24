from django import forms
from .models import ImportConfig

class ImportConfigForm(forms.ModelForm):
    class Meta:
        model = ImportConfig
        fields = [
            "vehicle", "name",
            "interval_minutes", "enabled",
            "editorial_xpaths", "listing_link_xpath",
            "article_section_name_xpath",
            "article_date_xpath", "article_title_xpath",
            "article_subtitle_xpath", "article_author_xpath",
            "article_content_xpath",
        ]
        widgets = {
            "editorial_xpaths": forms.Textarea(attrs={"rows": 5, "placeholder": "//nav//a[contains(.,'Sports')]/@href\n//nav//a[contains(.,'Economy')]/@href"}),
            "listing_link_xpath": forms.Textarea(attrs={"rows": 2, "placeholder": "//article//a/@href"}),
            "article_section_name_xpath": forms.Textarea(attrs={"rows": 2, "placeholder": "//span[@class='section']"}),
            "article_date_xpath": forms.Textarea(attrs={"rows": 2, "placeholder": "//time/@datetime | //time"}),
            "article_title_xpath": forms.Textarea(attrs={"rows": 2, "placeholder": "//h1"}),
            "article_subtitle_xpath": forms.Textarea(attrs={"rows": 2, "placeholder": "//h2"}),
            "article_author_xpath": forms.Textarea(attrs={"rows": 2, "placeholder": "//*[contains(@class,'author')]"}),
            "article_content_xpath": forms.Textarea(attrs={"rows": 3, "placeholder": "//*[contains(@class,'article-body')]"}),
        }
