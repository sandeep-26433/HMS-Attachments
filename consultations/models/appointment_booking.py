from odoo import api, fields, models, _
from datetime import datetime

class AppointmentBooking(models.Model):
    _name = "appointment.booking"
    _description = "Appointment Booking"

    patient_id = fields.Many2one(
        'res.partner', 
        string="Patient", 
        required=True, 
        help="Select existing patient or create a new one."
    )
    name = fields.Char(string="Patient Name", required=True)
    reference_id = fields.Char(string="Patient Reference ID")

    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('others', 'Others')
    ])

    date_of_birth = fields.Date(string="Date of Birth")
    age = fields.Integer(string="Age", compute='_compute_age', store=True)
    phone = fields.Char(string="Phone")
    email = fields.Char(string="Email")

    appointment_date = fields.Date(string="Appointment Date", required=True)
    op_number = fields.Char(string="OP Number", readonly=True, copy=False, default=lambda self: _('New'))

    department = fields.Selection([
        ('kayachikitsa', 'KAYACHIKITSA'),
        ('panchakarma', 'PANCHAKARMA'),
        ('streerogam_prasutitantra', 'STREEROGAM & PRASUTITANTRA'),
        ('kaumarabrityam', 'KAUMARABRITYAM'),
        ('shalyam', 'SHALAYAM'),
        ('shalakyam', 'SHALAKYAM'),
        ('swastavrittan', 'SWASTAVRITTAN'),
        ('emergency', 'EMERGENCY'),
        ('ip', 'IP'),
        ('counter_sales', 'COUNTER SALES')
    ], string="Department")

    consultation_doctor = fields.Many2one('consultation.doctor', string="Consultation Doctor")
    consultation_mode = fields.Selection([('online', 'Online'), ('offline', 'Offline')])
    if_online = fields.Text(string="If Online")
    referral = fields.Char(string="Referral(if Any)")
    priority = fields.Char(string="Priority")
    notes = fields.Text(string="Any Notes")

    # New Field: Patient Type (Old/New)
    patient_type = fields.Selection([
        ('new', 'New Patient'),
        ('old', 'Old Patient')
    ], string="Patient Type", compute="_compute_patient_type", store=True)

    # Pipeline Status Bar
    state = fields.Selection([
        ('booked', 'Appointment Booked'),
        ('completed', 'Consultation Completed'),
        ('cancelled', 'Cancelled')
    ], string="Status", default='booked', tracking=True, required=True)

    doctor_appointment_id = fields.Many2one(
        'doctor.appointments',
        string="Doctor Appointment",
        readonly=True,
        help="Automatically linked Doctor Appointment"
    )

    @api.depends('date_of_birth')
    def _compute_age(self):
        for record in self:
            if record.date_of_birth:
                today = datetime.today()
                birth_date = fields.Date.from_string(record.date_of_birth)
                record.age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            else:
                record.age = 0

    @api.depends('patient_id')
    def _compute_patient_type(self):
        """Determine if the patient is New or Old based on previous appointments"""
        for record in self:
            if record.patient_id:
                previous_appointments = self.env['appointment.booking'].search_count([
                    ('patient_id', '=', record.patient_id.id),
                    ('id', '!=', record.id)  # Exclude current appointment
                ])
                record.patient_type = 'old' if previous_appointments > 0 else 'new'
            else:
                record.patient_type = 'new'  # Default for new records

    @api.onchange('patient_id')
    def _onchange_patient_id(self):
        """Auto-fill patient details when selecting from dropdown and update patient type"""
        if self.patient_id:
            self.name = self.patient_id.name
            self.phone = self.patient_id.phone
            self.email = self.patient_id.email
            self._compute_patient_type()  # Recalculate patient type when patient is selected

    @api.model
    def create(self, vals):
        """Ensure OP Number is auto-generated and create doctor appointment"""
        if vals.get('op_number', 'New') == 'New':
            vals['op_number'] = self.env['ir.sequence'].next_by_code('appointment.op_number') or '0000'

        # Auto-fill name from patient_id if empty
        if vals.get('patient_id'):
            patient = self.env['res.partner'].browse(vals['patient_id'])
            vals['name'] = patient.name

        booking = super(AppointmentBooking, self).create(vals)

        # Automatically create a doctor appointment
        doctor_appointment = self.env['doctor.appointments'].create({
            'booking_id': booking.id,  # Linking to booking
            'patient_id': booking.patient_id.id,
            'appointment_date': booking.appointment_date,
            'reference_id': booking.reference_id,
            'state': booking.state,
        })

        # Link the doctor appointment to the booking
        booking.doctor_appointment_id = doctor_appointment.id

        return booking

    def action_cancel(self):
        """Cancel the appointment and update related doctor appointment"""
        self.write({'state': 'cancelled'})
        if self.doctor_appointment_id:
            self.doctor_appointment_id.write({'state': 'cancelled'})
