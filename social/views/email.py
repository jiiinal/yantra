from celery import shared_task
from django.core.mail import EmailMessage

FROM_EMAIL = 'fusioncorpmailbot@gmail.com'
class EMail:
    def __init__(self) -> None:
        self.from_email = FROM_EMAIL
        
        
    def send(self,subject, body, sendto:list, attach, filename, attachType):
        try:
            email = EmailMessage()
            email.subject = subject
            email.body = body
            email.from_email = self.from_email
            email.to = sendto
            email.attach(filename, attach.getvalue(), attachType)
            email.send() 
            return ''
        except Exception as e:
            return str(e)
        

