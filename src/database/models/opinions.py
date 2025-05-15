from sqlalchemy import Text, ForeignKey, UniqueConstraint, Boolean, CheckConstraint

from sqlalchemy.orm import mapped_column, Mapped, relationship, backref

from database import Base


class CommentModel(Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint(
            "movie_id", "user_id",
            name="uq_one_comment_per_movie_per_user"
        ),
        CheckConstraint(
            "is_like IS NOT NULL OR content IS NOT NULL",
            name="check_reaction_needed"
        )
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=True)
    is_like: Mapped[bool] = mapped_column(Boolean, nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id", ondelete="CASCADE"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    replies: Mapped[list["CommentModel"]] = relationship(
        "CommentModel",
        backref=backref("parent", remote_side=[id]),
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self):
        return f"<Comment(id={self.id}, content={self.content[:20]}..., movie_id={self.movie_id}, parent_id={self.parent_id})>"