# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2018-01-09 11:52
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('warehouse', '0013_auto_incrementing_batch_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='batch',
            name='dag_slug',
            field=models.CharField(default='no_slug', max_length=100),
            preserve_default=False,
        ),
    ]