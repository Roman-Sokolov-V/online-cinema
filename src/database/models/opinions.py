from sqlalchemy import Text, ForeignKey, UniqueConstraint

from sqlalchemy.orm import mapped_column, Mapped, relationship, backref

from database import Base


class CommentModel(Base):
    __tablename__ = "comments"
    __table_args__ = (
        UniqueConstraint(
            "movie_id", "user_id",
            name="uq_one_comment_per_movie_per_user"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=False)
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