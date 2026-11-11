"""
AI Systems API Router - Complete Implementation
This implements all functionality from the Node.js systemsController
"""

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
import asyncpg
from datetime import datetime
from ..shared.database import get_db_pool
from .auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/systems", tags=["ai-systems"])

# ============= REQUEST/RESPONSE MODELS =============

class AISystemCreate(BaseModel):
    """Create system request - matches frontend expectations"""
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    system_type: str = Field(default="llm")
    compliance_frameworks: List[str] = Field(default_factory=list)
    model_config_id: Optional[int] = None  # Primary model
    industry: Optional[str] = None

class AISystemUpdate(BaseModel):
    """Update system request"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[str] = None
    compliance_frameworks: Optional[List[str]] = None
    industry: Optional[str] = None

class AISystemResponse(BaseModel):
    """System response - matches frontend expectations EXACTLY"""
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
    system_id: int
    name: str
    description: Optional[str]
    version: Optional[str]
    system_type: str
    compliance_frameworks: List[str]
    model_name: Optional[str]  # Primary model name for display
    model_config_id: Optional[int]
    models: List[Dict[str, Any]]  # All assigned models
    industry: Optional[str]
    status: str = "active"
    last_tested: Optional[datetime]
    compliance_scores: Dict[str, float]
    created_at: datetime
    updated_at: Optional[datetime]

# ============= DATABASE CONNECTION =============

async def get_db_pool_dependency():
    """Get database connection pool"""
    return get_db_pool()

# ============= API ENDPOINTS =============

@router.get("/", response_model=List[AISystemResponse])
async def get_systems(
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """
    Get all AI systems for the current user.
    Implements Node.js getSystems logic exactly.
    """
    try:
        async with db_pool.acquire() as conn:
            # Get all systems with model count
            systems = await conn.fetch("""
                SELECT 
                    s.system_id,
                    s.name,
                    s.description,
                    s.version,
                    s.system_type,
                    s.model_config_id,
                    s.industry,
                    s.created_at,
                    s.updated_at,
                    s.user_id,
                    s.compliance_frameworks,
                    mc.name as model_name,
                    COUNT(DISTINCT smc.config_id) as model_count
                FROM ai_systems s
                LEFT JOIN ai_model_configs mc ON s.model_config_id = mc.config_id
                LEFT JOIN ai_system_model_configs smc ON s.system_id = smc.system_id
                WHERE s.user_id = $1
                GROUP BY s.system_id, mc.name, s.compliance_frameworks
                ORDER BY s.created_at DESC
            """, current_user['user_id'])
            
            result = []
            for sys in systems:
                # Get all models for this system
                models = await conn.fetch("""
                    SELECT 
                        mc.config_id,
                        mc.name,
                        mc.provider,
                        mc.model_id,
                        smc.model_role,
                        smc.is_primary
                    FROM ai_system_model_configs smc
                    JOIN ai_model_configs mc ON smc.config_id = mc.config_id
                    WHERE smc.system_id = $1
                    ORDER BY smc.is_primary DESC
                """, sys['system_id'])
                
                # Get compliance scores (average of test results)
                scores = await conn.fetch("""
                    SELECT 
                        test_name,
                        AVG(
                            CASE 
                                WHEN result = 'passed' THEN 100.0
                                WHEN result = 'failed' THEN 0.0
                                ELSE 50.0
                            END
                        ) as avg_score
                    FROM ai_model_test_results
                    WHERE system_id = $1
                    GROUP BY test_name
                """, sys['system_id'])
                
                compliance_scores = {
                    score['test_name']: float(score['avg_score']) 
                    for score in scores
                }
                
                # Get last test date
                last_test = await conn.fetchval("""
                    SELECT MAX(created_at) 
                    FROM ai_model_test_results 
                    WHERE system_id = $1
                """, sys['system_id'])
                
                result.append({
                    "system_id": sys['system_id'],
                    "name": sys['name'],
                    "description": sys['description'],
                    "version": sys['version'],
                    "system_type": sys['system_type'],
                    "compliance_frameworks": sys['compliance_frameworks'] or [],
                    "model_name": sys['model_name'],  # Primary model name
                    "model_config_id": sys['model_config_id'],
                    "models": [dict(m) for m in models],
                    "industry": sys['industry'],
                    "status": "active",
                    "last_tested": last_test,
                    "compliance_scores": compliance_scores,
                    "created_at": sys['created_at'],
                    "updated_at": sys['updated_at']
                })
            
            logger.info(f"Retrieved {len(result)} systems for user {current_user['user_id']}")
            return result
            
    except Exception as e:
        logger.error(f"Failed to get systems: {e}")
        raise HTTPException(500, f"Failed to retrieve systems: {str(e)}")

@router.get("/{system_id}", response_model=AISystemResponse)
async def get_system(
    system_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """Get a specific AI system by ID"""
    try:
        async with db_pool.acquire() as conn:
            system = await conn.fetchrow("""
                SELECT 
                    s.*,
                    mc.name as model_name
                FROM ai_systems s
                LEFT JOIN ai_model_configs mc ON s.model_config_id = mc.config_id
                WHERE s.system_id = $1 AND s.user_id = $2
            """, system_id, current_user['user_id'])
            
            if not system:
                raise HTTPException(404, "System not found")
            
            # Get models
            models = await conn.fetch("""
                SELECT 
                    mc.config_id,
                    mc.name,
                    mc.provider,
                    mc.model_id,
                    smc.model_role,
                    smc.is_primary
                FROM ai_system_model_configs smc
                JOIN ai_model_configs mc ON smc.config_id = mc.config_id
                WHERE smc.system_id = $1
            """, system_id)
            
            # Get compliance scores
            scores = await conn.fetch("""
                SELECT test_name, AVG(
                    CASE 
                        WHEN result = 'passed' THEN 100.0
                        WHEN result = 'failed' THEN 0.0
                        ELSE 50.0
                    END
                ) as avg_score
                FROM ai_model_test_results
                WHERE system_id = $1
                GROUP BY test_name
            """, system_id)
            
            compliance_scores = {s['test_name']: float(s['avg_score']) for s in scores}
            
            return {
                "system_id": system['system_id'],
                "name": system['name'],
                "description": system['description'],
                "version": system['version'],
                "system_type": system['system_type'],
                "compliance_frameworks": system['compliance_frameworks'] or [],
                "model_name": system['model_name'],
                "model_config_id": system['model_config_id'],
                "models": [dict(m) for m in models],
                "industry": system['industry'],
                "status": "active",
                "last_tested": None,
                "compliance_scores": compliance_scores,
                "created_at": system['created_at'],
                "updated_at": system['updated_at']
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get system {system_id}: {e}")
        raise HTTPException(500, f"Failed to retrieve system: {str(e)}")

@router.post("/", response_model=AISystemResponse, status_code=201)
async def create_system(
    system_data: AISystemCreate,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """
    Create a new AI system.
    Implements Node.js createSystem + createModel logic.
    """
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Create the system
                system = await conn.fetchrow("""
                    INSERT INTO ai_systems (
                        name, description, version, system_type,
                        compliance_frameworks, model_config_id, 
                        industry, user_id, created_at, updated_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                    RETURNING *
                """, 
                    system_data.name,
                    system_data.description,
                    system_data.version,
                    system_data.system_type,
                    system_data.compliance_frameworks,
                    system_data.model_config_id,
                    system_data.industry,
                    current_user['user_id']
                )
                
                # If model specified, add to junction table
                if system_data.model_config_id:
                    await conn.execute("""
                        INSERT INTO ai_system_model_configs (
                            system_id, config_id, model_role, is_primary, created_by
                        ) VALUES ($1, $2, 'primary', true, $3)
                    """, 
                        system['system_id'],
                        system_data.model_config_id,
                        current_user['user_id']
                    )
                    
                    # Get model name
                    model = await conn.fetchrow("""
                        SELECT name FROM ai_model_configs 
                        WHERE config_id = $1
                    """, system_data.model_config_id)
                    
                    model_name = model['name'] if model else None
                else:
                    model_name = None
                
                logger.info(f"Created system {system['system_id']} for user {current_user['user_id']}")
                
                return {
                    "system_id": system['system_id'],
                    "name": system['name'],
                    "description": system['description'],
                    "version": system['version'],
                    "system_type": system['system_type'],
                    "compliance_frameworks": system['compliance_frameworks'] or [],
                    "model_name": model_name,
                    "model_config_id": system['model_config_id'],
                    "models": [],
                    "industry": system['industry'],
                    "status": "active",
                    "last_tested": None,
                    "compliance_scores": {},
                    "created_at": system['created_at'],
                    "updated_at": system['updated_at']
                }
                
    except Exception as e:
        logger.error(f"Failed to create system: {e}")
        raise HTTPException(500, f"Failed to create system: {str(e)}")

@router.put("/{system_id}", response_model=AISystemResponse)
async def update_system(
    system_id: int,
    update_data: AISystemUpdate,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """Update an AI system"""
    try:
        async with db_pool.acquire() as conn:
            # Build update query dynamically
            updates = []
            values = []
            param_count = 1
            
            if update_data.name is not None:
                updates.append(f"name = ${param_count}")
                values.append(update_data.name)
                param_count += 1
            
            if update_data.description is not None:
                updates.append(f"description = ${param_count}")
                values.append(update_data.description)
                param_count += 1
            
            if update_data.version is not None:
                updates.append(f"version = ${param_count}")
                values.append(update_data.version)
                param_count += 1
            
            if update_data.compliance_frameworks is not None:
                updates.append(f"compliance_frameworks = ${param_count}")
                values.append(update_data.compliance_frameworks)
                param_count += 1
            
            if update_data.industry is not None:
                updates.append(f"industry = ${param_count}")
                values.append(update_data.industry)
                param_count += 1
            
            if not updates:
                raise HTTPException(400, "No fields to update")
            
            updates.append(f"updated_at = NOW()")
            values.extend([system_id, current_user['user_id']])
            
            query = f"""
                UPDATE ai_systems 
                SET {', '.join(updates)}
                WHERE system_id = ${param_count} AND user_id = ${param_count + 1}
                RETURNING *
            """
            
            system = await conn.fetchrow(query, *values)
            
            if not system:
                raise HTTPException(404, "System not found")
            
            # Get updated system with models
            return await get_system(system_id, current_user, db_pool)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update system {system_id}: {e}")
        raise HTTPException(500, f"Failed to update system: {str(e)}")

@router.delete("/{system_id}", status_code=204)
async def delete_system(
    system_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """Delete an AI system and all associated data"""
    try:
        async with db_pool.acquire() as conn:
            async with conn.transaction():
                # Delete test results first
                await conn.execute("""
                    DELETE FROM ai_model_test_results WHERE system_id = $1
                """, system_id)
                
                # Delete model associations
                await conn.execute("""
                    DELETE FROM ai_system_model_configs WHERE system_id = $1
                """, system_id)
                
                # Delete the system
                result = await conn.execute("""
                    DELETE FROM ai_systems 
                    WHERE system_id = $1 AND user_id = $2
                """, system_id, current_user['user_id'])
                
                if result == "DELETE 0":
                    raise HTTPException(404, "System not found")
                
                logger.info(f"Deleted system {system_id} for user {current_user['user_id']}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete system {system_id}: {e}")
        raise HTTPException(500, f"Failed to delete system: {str(e)}")

# ============= MODEL MANAGEMENT ENDPOINTS =============

@router.post("/{system_id}/models", status_code=201)
async def add_model_to_system(
    system_id: int,
    model_data: Dict[str, Any],
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """
    Add a model to a system.
    Implements Node.js createModel logic.
    """
    try:
        async with db_pool.acquire() as conn:
            # Verify system ownership
            system = await conn.fetchrow("""
                SELECT * FROM ai_systems 
                WHERE system_id = $1 AND user_id = $2
            """, system_id, current_user['user_id'])
            
            if not system:
                raise HTTPException(404, "System not found")
            
            # Add model to system
            config_id = model_data.get('config_id')
            role = model_data.get('role', 'primary')
            is_primary = model_data.get('is_primary', False)
            
            if is_primary:
                # Unset other primary models
                await conn.execute("""
                    UPDATE ai_system_model_configs 
                    SET is_primary = false 
                    WHERE system_id = $1
                """, system_id)
                
                # Update system's primary model
                await conn.execute("""
                    UPDATE ai_systems 
                    SET model_config_id = $1 
                    WHERE system_id = $2
                """, config_id, system_id)
            
            await conn.execute("""
                INSERT INTO ai_system_model_configs (
                    system_id, config_id, model_role, is_primary, created_by
                ) VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (system_id, config_id) 
                DO UPDATE SET 
                    model_role = EXCLUDED.model_role,
                    is_primary = EXCLUDED.is_primary
            """, system_id, config_id, role, is_primary, current_user['user_id'])
            
            return {"success": True, "message": "Model added to system"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add model to system {system_id}: {e}")
        raise HTTPException(500, f"Failed to add model: {str(e)}")

@router.delete("/{system_id}/models/{config_id}", status_code=204)
async def remove_model_from_system(
    system_id: int,
    config_id: int,
    current_user: dict = Depends(get_current_user),
    db_pool = Depends(get_db_pool_dependency)
):
    """Remove a model from a system"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute("""
                DELETE FROM ai_system_model_configs 
                WHERE system_id = $1 AND config_id = $2
                AND system_id IN (
                    SELECT system_id FROM ai_systems WHERE user_id = $3
                )
            """, system_id, config_id, current_user['user_id'])
            
            if result == "DELETE 0":
                raise HTTPException(404, "Model not found in system")
            
            # If this was the primary model, clear it
            await conn.execute("""
                UPDATE ai_systems 
                SET model_config_id = NULL 
                WHERE system_id = $1 AND model_config_id = $2
            """, system_id, config_id)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove model from system: {e}")
        raise HTTPException(500, f"Failed to remove model: {str(e)}")