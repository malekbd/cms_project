from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0011_branch_target_daily_user_entry'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='is_new_user',
            field=models.BooleanField(default=False, help_text='Indicates if this solved ticket added a new user'),
        ),
        migrations.AddField(
            model_name='ticket',
            name='new_user_id',
            field=models.CharField(blank=True, help_text='New user/customer identifier created after solving', max_length=100, null=True),
        ),
        migrations.DeleteModel(
            name='DailyUserEntry',
        ),
        migrations.DeleteModel(
            name='BranchTarget',
        ),
    ]
