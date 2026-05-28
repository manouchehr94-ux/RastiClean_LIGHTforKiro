from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.notifications.models import NotificationSetting
from apps.notifications.sync import (
    sync_notification_setting_from_sms_template,
    sync_sms_template_from_notification_setting,
)


@receiver(post_save, sender=NotificationSetting)
def notification_setting_saved(sender, instance: NotificationSetting, **kwargs):
    """
    When admin changes SMS enabled/disabled from notification settings,
    update the matching SMS template active state automatically.
    """
    sync_sms_template_from_notification_setting(setting=instance)


def connect_sms_template_signal() -> None:
    """
    Import SMSTemplate lazily to avoid circular app-loading issues.
    Called from NotificationsConfig.ready().
    """
    try:
        from apps.sms.models import SMSTemplate
    except Exception:
        return

    post_save.connect(
        sms_template_saved,
        sender=SMSTemplate,
        dispatch_uid="rasti_sms_template_saved_sync_notification_setting",
        weak=False,
    )


def sms_template_saved(sender, instance, **kwargs):
    """
    When admin changes a template active/inactive state,
    update the matching NotificationSetting.sms_enabled automatically.
    """
    sync_notification_setting_from_sms_template(template=instance)