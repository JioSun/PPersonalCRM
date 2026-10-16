from celery import Celery

app = Celery(
    'personalcrm_tasks',
    broker='redis://redis:6379/1',
    backend='redis://redis:6379/2',
    include=[
        'backend.app.celery_tasks.email_tasks.tasks',
    ],
)

app.conf.task_routes = {
    'send_invoice_email': {'queue': 'email_queue'},
}
