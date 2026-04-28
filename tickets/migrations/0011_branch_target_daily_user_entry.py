from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0010_ticket_is_partner'),
    ]

    operations = [
        migrations.CreateModel(
            name='BranchTarget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('month', models.PositiveSmallIntegerField(validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)])),
                ('year', models.PositiveIntegerField(validators=[django.core.validators.MinValueValidator(2000), django.core.validators.MaxValueValidator(9999)])),
                ('monthly_user_target', models.PositiveIntegerField(default=0)),
                ('yearly_user_target', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='branch_targets', to='tickets.branchoption')),
            ],
            options={
                'verbose_name': 'Branch Target',
                'verbose_name_plural': 'Branch Targets',
                'ordering': ['-year', '-month', 'branch__display_name'],
            },
        ),
        migrations.CreateModel(
            name='DailyUserEntry',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('new_users_added', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='daily_user_entries', to='tickets.branchoption')),
            ],
            options={
                'verbose_name': 'Daily User Entry',
                'verbose_name_plural': 'Daily User Entries',
                'ordering': ['-date', 'branch__display_name'],
            },
        ),
        migrations.AddIndex(
            model_name='branchtarget',
            index=models.Index(fields=['year', 'month'], name='tickets_bra_year_739c72_idx'),
        ),
        migrations.AddConstraint(
            model_name='branchtarget',
            constraint=models.UniqueConstraint(fields=('branch', 'month', 'year'), name='unique_branch_target_period'),
        ),
        migrations.AddIndex(
            model_name='dailyuserentry',
            index=models.Index(fields=['date'], name='tickets_dai_date_692e17_idx'),
        ),
        migrations.AddIndex(
            model_name='dailyuserentry',
            index=models.Index(fields=['branch', 'date'], name='tickets_dai_branch__9b31d8_idx'),
        ),
        migrations.AddConstraint(
            model_name='dailyuserentry',
            constraint=models.UniqueConstraint(fields=('branch', 'date'), name='unique_branch_daily_user_entry'),
        ),
    ]
