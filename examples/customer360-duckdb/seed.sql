-- Deterministic synthetic observations. Audit instants record fixture construction.
INSERT INTO domain.customer_keymap VALUES
 (1,'C001','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),(2,'C002','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (3,'C003','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO domain.customer VALUES
 (1,'C001','Alex Example','standard','2025-01-01 00:00:00+00','2025-02-01 00:00:00+00',false,false,NULL,'2025-01-01 00:00:00+00','2025-02-01 00:00:00+00'),
 (1,'C001','Alex Example','premium','2025-02-01 00:00:00+00','infinity',true,false,NULL,'2025-02-01 00:00:00+00','2025-02-01 00:00:00+00'),
 (2,'C002','Sam Synthetic','standard','2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (3,'C003','Retired Example','standard','2025-01-01 00:00:00+00','2025-02-01 00:00:00+00',false,false,NULL,'2025-01-01 00:00:00+00','2025-02-01 00:00:00+00'),
 (3,'C003','Retired Example','standard','2025-02-01 00:00:00+00','infinity',true,true,'2025-02-01 00:00:00+00','2025-02-01 00:00:00+00','2025-02-01 00:00:00+00');
INSERT INTO domain.product_keymap VALUES
 (1,'P001','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),(2,'P002','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),(3,'P003','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO domain.product VALUES
 (1,'P001','Saver','Savings account for planned reserves.','2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (2,'P002','Everyday','Payments account for everyday purchases.','2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (3,'P003','Flex','Credit facility for short term borrowing.','2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO domain.account_keymap VALUES
 (1,'A001','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),(2,'A002','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),(3,'A003','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO domain.account VALUES
 (1,'A001',1,1,'2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (2,'A002',1,2,'2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (3,'A003',2,3,'2025-01-01 00:00:00+00','infinity',true,false,NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO domain.transaction_keymap
SELECT i, 'T'||lpad(i::VARCHAR,3,'0'),'2025-01-01 00:00:00+00'::TIMESTAMPTZ,'2025-01-01 00:00:00+00'::TIMESTAMPTZ FROM range(1,13) r(i);
INSERT INTO domain.transaction
SELECT i,'T'||lpad(i::VARCHAR,3,'0'),1+(i-1)%3,10*i,
       '2025-01-01 00:00:00+00'::TIMESTAMPTZ+i*INTERVAL '3 days',
       '2025-01-01 00:00:00+00'::TIMESTAMPTZ+i*INTERVAL '3 days','infinity'::TIMESTAMPTZ,true,false,NULL,
       '2025-01-01 00:00:00+00'::TIMESTAMPTZ+i*INTERVAL '3 days','2025-01-01 00:00:00+00'::TIMESTAMPTZ+i*INTERVAL '3 days'
FROM range(1,13) r(i);

INSERT INTO search.entity_embedding
SELECT product_id,product_id,'PRODUCT','domain','description',search.embed(description),3,'toy-lexical-v1','1',
       '2025-01-01 00:00:00+00'::TIMESTAMPTZ,'IN_DATABASE','2025-01-01 00:00:00+00'::TIMESTAMPTZ,'infinity'::TIMESTAMPTZ,true,false,NULL,
       '2025-01-01 00:00:00+00'::TIMESTAMPTZ,'2025-01-01 00:00:00+00'::TIMESTAMPTZ
FROM domain.v_product;

-- Source cutoff uses the same instant on every contributing entity.
INSERT INTO prediction.feature_value
WITH snapshots AS (SELECT '2025-02-01 00:00:00+00'::TIMESTAMPTZ AS observation_dts, '2025-03-01 00:00:00+00'::TIMESTAMPTZ AS until_dts
 UNION ALL SELECT '2025-03-01 00:00:00+00'::TIMESTAMPTZ,'infinity'::TIMESTAMPTZ), totals AS (
 SELECT c.customer_id,s.observation_dts,s.until_dts,least(1,greatest(0,coalesce(sum(t.amount),0)/1000)) AS intensity
 FROM snapshots s JOIN domain.customer c ON c.valid_from_dts<=s.observation_dts AND s.observation_dts<c.valid_to_dts AND NOT c.is_deleted
 LEFT JOIN domain.account a ON a.customer_id=c.customer_id AND a.valid_from_dts<=s.observation_dts AND s.observation_dts<a.valid_to_dts AND NOT a.is_deleted
 LEFT JOIN domain.transaction t ON t.account_id=a.account_id AND t.posted_dts<s.observation_dts AND t.valid_from_dts<=s.observation_dts AND s.observation_dts<t.valid_to_dts AND NOT t.is_deleted
 GROUP BY c.customer_id,s.observation_dts,s.until_dts
)
SELECT customer_id,customer_id,'CUSTOMER','spend_intensity','1',intensity,observation_dts,
 observation_dts,until_dts,until_dts='infinity'::TIMESTAMPTZ,false,NULL,observation_dts,observation_dts FROM totals;
INSERT INTO prediction.model_prediction
SELECT entity_id,entity_id,'CUSTOMER','toy-score-v1','1',1-value_numeric,observation_dts,observation_dts,
 valid_from_dts,valid_to_dts,is_current,false,NULL,created_dts,updated_dts FROM prediction.feature_value;

INSERT INTO observability.data_lineage VALUES
 (1,'domain.product','search.entity_embedding','embed-products','search.embed(description)',true,'2025-01-01 00:00:00+00',NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (2,'domain.transaction','prediction.feature_value','monthly-features','Clipped spend by customer at source cutoff',true,'2025-01-01 00:00:00+00',NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 (3,'prediction.feature_value','prediction.model_prediction','toy-score','1 - spend_intensity',true,'2025-01-01 00:00:00+00',NULL,'2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO observability.lineage_run VALUES
 (1,1,'2025-03-01 00:00:00+00','SUCCESS',3,3,'fixture','2025-03-01 00:00:00+00','2025-03-01 00:00:00+00'),
 (2,2,'2025-03-01 00:00:00+00','SUCCESS',12,4,'fixture','2025-03-01 00:00:00+00','2025-03-01 00:00:00+00'),
 (3,3,'2025-03-01 00:00:00+00','SUCCESS',4,4,'fixture','2025-03-01 00:00:00+00','2025-03-01 00:00:00+00');
INSERT INTO observability.change_event VALUES
 (1,'domain.customer','INSERT','2025-03-01 00:00:00+00','fixture-builder',5,'fixture','2025-03-01 00:00:00+00','2025-03-01 00:00:00+00');
INSERT INTO observability.data_quality_metric
SELECT 1,'domain.customer','COMPLETENESS',count(display_name)::DOUBLE/count(*),'2025-03-01 00:00:00+00'::TIMESTAMPTZ,
 1.0,true,count(*),'2025-03-01 00:00:00+00'::TIMESTAMPTZ,'2025-03-01 00:00:00+00'::TIMESTAMPTZ FROM domain.customer;
INSERT INTO observability.retention_policy VALUES
 ('definitions',NULL,'Retain lineage and documentation for product life.','product-owner','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 ('events',90,'Synthetic operational evidence window.','product-operator','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00'),
 ('validation',365,'Preserve historical validation evidence.','product-operator','2025-01-01 00:00:00+00','2025-01-01 00:00:00+00');
INSERT INTO memory.agent_session VALUES
 (1,'demo-session','demo-agent','demo-user','2025-03-01 00:00:00+00',NULL,'ACTIVE','Discover product trust and join paths','{"stage":"orientation"}',
 'USER','demo-user','2025-03-01 00:00:00+00','2025-03-01 00:00:00+00');
INSERT INTO memory.agent_interaction VALUES
 (1,1,1,'2025-03-01 00:00:00+00','QUERY','semantic.data_product_registry','SELECT product_id FROM semantic.data_product_registry',1,'SUCCESS',
 'USER','demo-user','2025-03-01 00:00:00+00','2025-03-01 00:00:00+00');
INSERT INTO observability.agent_outcome VALUES
 (1,'demo-agent','demo-session','QUERY','2025-03-01 00:00:00+00','semantic.data_product_registry','SUCCESS',1,'2025-03-01 00:00:00+00','2025-03-01 00:00:00+00');
