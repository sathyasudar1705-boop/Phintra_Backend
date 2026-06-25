"""add training and admin isolation columns

Revision ID: 20260610_training_isolation
Revises: 
Create Date: 2026-06-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260610_training_isolation'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # 1. Add admin_id to existing tables
    op.add_column('companies', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('departments', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('employees', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('campaigns', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('email_templates', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('email_logs', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('reported_emails', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('quizzes', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('certificates', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))

    # 2. Add columns to training_modules
    op.add_column('training_modules', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('training_modules', sa.Column('category', sa.String(), nullable=True))
    op.add_column('training_modules', sa.Column('duration', sa.Integer(), server_default='10', nullable=False))
    op.add_column('training_modules', sa.Column('difficulty', sa.String(), nullable=True))
    op.add_column('training_modules', sa.Column('video_url', sa.String(), nullable=True))
    op.add_column('training_modules', sa.Column('uploaded_video_url', sa.String(), nullable=True))

    # Make training_modules.admin_id NOT NULL after backfill in practice, but keep it nullable in migration for safety
    # op.alter_column('training_modules', 'admin_id', nullable=False)

    # 3. Modify training_assignments
    op.add_column('training_assignments', sa.Column('admin_id', sa.UUID(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=True))
    op.add_column('training_assignments', sa.Column('training_module_id', sa.UUID(), sa.ForeignKey('training_modules.id', ondelete='CASCADE'), nullable=True))
    op.add_column('training_assignments', sa.Column('department_id', sa.UUID(), sa.ForeignKey('departments.id', ondelete='CASCADE'), nullable=True))
    op.add_column('training_assignments', sa.Column('company_id', sa.UUID(), sa.ForeignKey('companies.id', ondelete='CASCADE'), nullable=True))
    op.alter_column('training_assignments', 'employee_id', nullable=True)

    # 4. Create training_completions
    op.create_table(
        'training_completions',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('training_module_id', sa.UUID(), sa.ForeignKey('training_modules.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_id', sa.UUID(), sa.ForeignKey('employees.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.Enum('NOT_STARTED', 'IN_PROGRESS', 'COMPLETED', name='completionstatus'), nullable=False, default='NOT_STARTED'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    )

def downgrade():
    op.drop_table('training_completions')
    op.alter_column('training_assignments', 'employee_id', nullable=False)
    op.drop_column('training_assignments', 'company_id')
    op.drop_column('training_assignments', 'department_id')
    op.drop_column('training_assignments', 'training_module_id')
    op.drop_column('training_assignments', 'admin_id')

    op.drop_column('training_modules', 'uploaded_video_url')
    op.drop_column('training_modules', 'video_url')
    op.drop_column('training_modules', 'difficulty')
    op.drop_column('training_modules', 'duration')
    op.drop_column('training_modules', 'category')
    op.drop_column('training_modules', 'admin_id')

    op.drop_column('certificates', 'admin_id')
    op.drop_column('quizzes', 'admin_id')
    op.drop_column('reported_emails', 'admin_id')
    op.drop_column('email_logs', 'admin_id')
    op.drop_column('email_templates', 'admin_id')
    op.drop_column('campaigns', 'admin_id')
    op.drop_column('employees', 'admin_id')
    op.drop_column('departments', 'admin_id')
    op.drop_column('companies', 'admin_id')
