from celery import shared_task
from django.utils import timezone

from trading.Strategies import swing
from trading.models import Scripts
from datetime import datetime


@shared_task(bind=True)
def fillScriptsExpiryDate(self):
    try:
        scripts = Scripts.objects.exclude(expiry__isnull=True).exclude(expiry='').exclude(expiryDate__isnull=False)

        updated_count = 0
        failed_count = 0

        for script in scripts:
            try:
                expiry_date = parse_flexible_date(script.expiry)
                if expiry_date:
                    script.expiryDate = expiry_date
                    script.save(update_fields=['expiryDate'])
                    updated_count += 1
                else:
                    print(f"Could not parse date for script {script.id}: {script.expiry}")
                    failed_count += 1
            except Exception as e:
                print(f"Error processing script {script.id}: {script.expiry} - Error: {e}")
                failed_count += 1

        print(f"Updated {updated_count} scripts with expiryDate")
        print(f"Failed to parse {failed_count} scripts")
        today = timezone.now().date()
        deleted_count, _ = Scripts.objects.filter(expiryDate__lt=today).delete()
        print(f"SyncSymbolsExpiry Deleted {deleted_count} expired scripts")

    except Exception as e:
        print(f"Task failed: {str(e)}")


def parse_flexible_date(date_str):
    """
    Parse multiple date formats:
    - 30-MAR-2026 (day-month_name-year)
    - 05-08-2025 (day-month-year or month-day-year)
    - 30-Mar-2026 (day-Month-year)
    """
    if not date_str:
        return None

    # Format 1: Try DD-MMM-YYYY (e.g., 30-MAR-2026 or 30-Mar-2026)
    try:
        expiry_normalized = '-'.join([
            date_str.split('-')[0],  # day
            date_str.split('-')[1].capitalize(),  # month (MAR -> Mar)
            date_str.split('-')[2]  # year
        ])
        return datetime.strptime(expiry_normalized, '%d-%b-%Y').date()
    except (ValueError, IndexError, AttributeError):
        pass

    # Format 2: Try DD-MM-YYYY (e.g., 05-08-2025)
    try:
        return datetime.strptime(date_str, '%d-%m-%Y').date()
    except ValueError:
        pass

    # # Format 3: Try MM-DD-YYYY (in case format is ambiguous)
    # try:
    #     return datetime.strptime(date_str, '%m-%d-%Y').date()
    # except ValueError:
    #     pass
    #
    # # Format 4: Try other common formats
    # for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
    #     try:
    #         return datetime.strptime(date_str, fmt).date()
    #     except ValueError:
    #         continue

    return None
