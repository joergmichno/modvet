import Stripe from 'stripe'

// The key comes from .env at run time. Claude never sees it.
export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY)
