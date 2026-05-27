"""
Utility functions for Rapid Cash system
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum, Count
from .models import Tarif, Transaction, Devise, Role, TypeOperation, StatutTransaction, Caisse, Commission, ContratPartenaire
import logging

logger = logging.getLogger(__name__)


def calculate_fee(montant, zone):
    """
    Calculate fees based on amount and zone tarification grid.
    
    Args:
        montant (Decimal): Transaction amount
        zone: ZoneTarif instance
    
    Returns:
        Decimal: Calculated fee
    """
    if not montant or not zone:
        return Decimal('0.00')
    
    try:
        montant = Decimal(str(montant))
        tarif = Tarif.objects.filter(
            zone=zone,
            montant_min__lte=montant,
            montant_max__gte=montant
        ).first()
        
        if tarif:
            return Decimal(str(tarif.frais_fixe))
        else:
            logger.warning(f"No tarif found for montant {montant} in zone {zone}")
            return Decimal('0.00')
    except (TypeError, ValueError) as e:
        logger.error(f"Error calculating fee: {e}")
        return Decimal('0.00')


def get_conversion_rate(devise_origine, devise_cible=None):
    """
    Get conversion rate between two currencies.
    Defaults to USD as reference currency.
    
    Args:
        devise_origine: Source Devise instance
        devise_cible: Target Devise instance (default: USD)
    
    Returns:
        Decimal: Conversion rate
    """
    if devise_cible is None:
        try:
            devise_cible = Devise.objects.get(code='USD')
        except Devise.DoesNotExist:
            logger.error("USD devise not found")
            return Decimal('1.0000')
    
    if devise_origine == devise_cible:
        return Decimal('1.0000')
    
    try:
        # Conversion formula: amount in origine * (usd_taux_cible / usd_taux_origine)
        rate = devise_cible.taux_reference_usd / devise_origine.taux_reference_usd
        return rate
    except (TypeError, ValueError, ZeroDivisionError) as e:
        logger.error(f"Error calculating conversion rate: {e}")
        return Decimal('1.0000')


@transaction.atomic
def create_transaction(agent, type_operation, montant, devise_origine, zone, observation=""):
    """
    Create a transaction with automatic fee calculation and caisse updates.
    This function ensures data consistency using atomic transactions.
    
    Args:
        agent: CustomUser instance (must be AGENT or ADMIN)
        type_operation: TypeOperation choice
        montant: Transaction amount
        devise_origine: Devise instance
        zone: ZoneTarif instance
        observation: Optional observation text
    
    Returns:
        Transaction: Created transaction instance or None if error
    
    Raises:
        ValueError: If validation fails
    """
    # Validation
    if agent.role not in [Role.ADMIN, Role.AGENT, Role.ASSOCIE]:
        raise ValueError(f"User {agent.username} is not an agent, admin, or associate")
    
    if type_operation not in dict(TypeOperation.choices).keys():
        raise ValueError(f"Invalid operation type: {type_operation}")
    
    try:
        montant = Decimal(str(montant))
        if montant <= 0:
            raise ValueError("Amount must be greater than 0")
    except (TypeError, ValueError) as e:
        raise ValueError(f"Invalid amount: {e}")
    
    # Check if agent has a caisse
    try:
        caisse = agent.caisse
    except Caisse.DoesNotExist:
        raise ValueError(f"Agent {agent.username} has no associated caisse")
    
    try:
        # Calculate fees
        frais_calcules = calculate_fee(montant, zone)
        
        # Get conversion rate to USD
        usd_devise = Devise.objects.get(code='USD')
        taux_conversion = get_conversion_rate(devise_origine, usd_devise)
        
        montant_reference = montant * taux_conversion
        frais_reference = frais_calcules * taux_conversion
        
        # Generate transaction number
        import uuid
        numero_transaction = f"TX-{uuid.uuid4().hex[:8].upper()}"
        
        # Create transaction
        transaction_obj = Transaction.objects.create(
            numero_transaction=numero_transaction,
            agent=agent,
            type_operation=type_operation,
            montant=montant,
            devise_origine=devise_origine,
            taux_conversion=taux_conversion,
            frais_calcules=frais_calcules,
            montant_reference=montant_reference,
            frais_reference=frais_reference,
            observation=observation,
            statut=StatutTransaction.COMPLETED
        )
        
        # Update caisse balance
        if type_operation == TypeOperation.TRANSFERT:
            caisse.solde += montant
        elif type_operation == TypeOperation.RETRAIT:
            caisse.solde -= montant
        
        caisse.save()
        
        logger.info(f"Transaction created: {numero_transaction} by {agent.username}")
        return transaction_obj
        
    except Exception as e:
        logger.error(f"Error creating transaction: {e}", exc_info=True)
        raise


def get_agent_performance_metrics(agent):
    """
    Calculate performance metrics for an agent.
    
    Returns:
        dict: Performance data
    """
    transactions = Transaction.objects.filter(
        agent=agent,
        statut=StatutTransaction.COMPLETED
    )

    total_transactions = transactions.count()
    total_volume = transactions.aggregate(total=Sum('montant_reference'))['total'] or Decimal('0.00')
    total_fees = transactions.aggregate(total=Sum('frais_reference'))['total'] or Decimal('0.00')
    total_commissions = Commission.objects.filter(agent=agent).aggregate(total=Sum('montant_commission'))['total'] or Decimal('0.00')

    return {
        'total_transactions': total_transactions,
        'total_volume': total_volume,
        'total_fees': total_fees,
        'total_commissions': total_commissions,
        'average_transaction': total_volume / total_transactions if total_transactions > 0 else Decimal('0.00'),
    }


def get_partner_balance(partner):
    """
    Calculate remaining balance for a partner (Associate or Investor).
    
    Returns:
        dict: Contract summary
    """
    contrats = partner.contrats.all()
    
    total_engaged = sum(c.montant_engage for c in contrats) or Decimal('0.00')
    total_paid = sum(c.montant_paye for c in contrats) or Decimal('0.00')
    balance = total_engaged - total_paid
    
    return {
        'total_engaged': total_engaged,
        'total_paid': total_paid,
        'balance': balance,
        'contract_count': contrats.count(),
    }
