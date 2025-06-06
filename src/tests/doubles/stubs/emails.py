from notifications import EmailSenderInterface


class StubEmailSender(EmailSenderInterface):

    async def send_activation_email(
            self, email: str, activation_link: str, activation_token: str
    ) -> None:
        """
        Stub implementation for sending an activation email.

        Args:
            email (str): The recipient's email address.
            activation_link (str): The activation link to include in the email.
            activation_token: (str): The activation token to include in the email.
        """
        return None

    async def send_activation_complete_email(self, email: str,
                                             login_link: str) -> None:
        """
        Stub implementation for sending an account activation complete email.

        Args:
            email (str): The recipient's email address.
            login_link (str): The login link to include in the email.
        """
        return None

    async def send_password_reset_email(self, email: str,
                                        reset_link: str) -> None:
        """
        Stub implementation for sending a password reset email.

        Args:
            email (str): The recipient's email address.
            reset_link (str): The password reset link to include in the email.
        """
        return None

    async def send_password_reset_complete_email(self, email: str,
                                                 login_link: str) -> None:
        """
        Stub implementation for sending a password reset complete email.

        Args:
            email (str): The recipient's email address.
            login_link (str): The login link to include in the email.
        """
        return None

    async def send_activity_notificator(
            self,
            email: str,
            comment_id: int,
            comment_content: str,
            reply_id: int,
            movie_title: str,
            is_like: bool | None = None,
            reply_content: str | None = None,
    ) -> None:
        """
        Stub implementation for notify users when their comments receive
         replies or likes email asynchronously.

        Args:
        email (str): The recipient's email address.
        comment_id(int): The id of the comment on which reply was given.
        comment_content (str): The content of the comment on which reply was given.
        reply_id(int): The id of the reply on which reply was given.
        reply_content (str): The content of the reply on which reply was given.
        is_like(bool): Whether the comment is like.
        movie_title(str): title of the movie.
        """
        return None


    async def send_payments_status(
            self,
            email: str,
            payments_status: str
    ) -> None:
        """
        Notify the user that the payment was successful or canceled

        Args:
        email (str): The recipient's email address.
        payments_status (StatusPayment): Payments status of the payment.
        """
        pass
